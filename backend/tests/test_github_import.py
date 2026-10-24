import base64
import os
import unittest
from unittest.mock import patch

import httpx
import mongomock
from fastapi import HTTPException, Response
from pymongo.errors import AutoReconnect

from app.models import PROFILES, PROJECTS
from app.routers import projects
from app.schema import GitHubImportRequest, ProjectReviewRequest
from app.services.github_service import (
    GitHubImportError,
    classify_project,
    fetch_github_repository,
    parse_repository_url,
)


def api_response(request):
    if request.url.path == "/repos/example/project":
        return httpx.Response(
            200,
            json={
                "name": "project",
                "owner": {"login": "example"},
                "description": "A React web application",
                "html_url": "https://github.com/example/project",
                "language": "JavaScript",
                "topics": ["react"],
            },
        )
    if request.url.path == "/repos/example/project/readme":
        encoded_readme = base64.b64encode(
            b"# Project\nA React and FastAPI full-stack portfolio."
        ).decode()
        return httpx.Response(
            200,
            json={"content": encoded_readme, "encoding": "base64"},
        )
    return httpx.Response(404, json={"message": "Not Found"})


class GitHubImportTests(unittest.TestCase):
    def setUp(self):
        self.client = mongomock.MongoClient()
        self.db = self.client.portfolio_chatbot
        self.profile_id = self.db[PROFILES].insert_one(
            {"name": "Chaitanya"}
        ).inserted_id

    def tearDown(self):
        self.client.close()

    def test_valid_repository_url_is_normalized(self):
        request = GitHubImportRequest(
            github_url="https://github.com/example/project.git"
        )
        self.assertEqual(
            parse_repository_url(request.github_url),
            ("example", "project", "https://github.com/example/project"),
        )

    def test_invalid_and_deceptive_urls_are_rejected(self):
        for url in (
            "http://github.com/example/project",
            "https://github.com.example.org/example/project",
            "https://user:pass@github.com/example/project",
            "https://github.com/example/project/issues",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                GitHubImportRequest(github_url=url)

    def test_github_api_fetches_metadata_and_bounded_readme(self):
        repository = fetch_github_repository(
            "https://github.com/example/project",
            transport=httpx.MockTransport(api_response),
        )

        self.assertEqual(repository.name, "project")
        self.assertEqual(repository.owner, "example")
        self.assertEqual(repository.language, "JavaScript")
        self.assertEqual(repository.category, "Full-stack projects")
        self.assertIn("FastAPI", repository.readme_summary)

    def test_missing_repository_returns_not_found(self):
        with self.assertRaises(GitHubImportError) as error:
            fetch_github_repository(
                "https://github.com/example/missing",
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(404, json={"message": "Not Found"})
                ),
            )
        self.assertEqual(error.exception.status_code, 404)

    def test_missing_readme_is_optional(self):
        def handler(request):
            if request.url.path.endswith("/readme"):
                return httpx.Response(404)
            return httpx.Response(
                200,
                json={
                    "name": "project",
                    "description": "Project description",
                    "language": "Python",
                    "topics": [],
                },
            )

        repository = fetch_github_repository(
            "https://github.com/example/project",
            transport=httpx.MockTransport(handler),
        )
        self.assertIsNone(repository.readme_summary)
        self.assertEqual(repository.description, "Project description")

    def test_rate_limit_and_timeout_are_reported(self):
        with self.assertRaises(GitHubImportError) as rate_limit:
            fetch_github_repository(
                "https://github.com/example/project",
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        403,
                        headers={"x-ratelimit-remaining": "0"},
                        json={"message": "rate limit"},
                    )
                ),
            )
        self.assertEqual(rate_limit.exception.status_code, 429)

        def timeout(request):
            raise httpx.ReadTimeout("timeout", request=request)

        with self.assertRaises(GitHubImportError) as timeout_error:
            fetch_github_repository(
                "https://github.com/example/project",
                transport=httpx.MockTransport(timeout),
            )
        self.assertEqual(timeout_error.exception.status_code, 504)

    def test_import_saves_pending_project_and_duplicate_is_idempotent(self):
        repository = fetch_github_repository(
            "https://github.com/example/project",
            transport=httpx.MockTransport(api_response),
        )
        with patch.object(projects, "fetch_github_repository", return_value=repository):
            response = projects.import_github_project(
                GitHubImportRequest(github_url="https://github.com/example/project"),
                Response(),
                self.db,
            )
        self.assertEqual(response.status, "pending_review")
        self.assertEqual(response.source_type, "github")
        self.assertEqual(response.import_status, "imported")
        self.assertIsNone(response.role)
        self.assertIsNone(response.deployed_url)
        self.assertEqual(self.db[PROJECTS].count_documents({}), 1)

        duplicate_response = Response()
        with patch.object(projects, "fetch_github_repository") as fetch:
            duplicate = projects.import_github_project(
                GitHubImportRequest(github_url="https://github.com/example/project"),
                duplicate_response,
                self.db,
            )
        fetch.assert_not_called()
        self.assertEqual(duplicate.import_status, "already_exists")
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(self.db[PROJECTS].count_documents({}), 1)

    def test_database_failure_does_not_store_import(self):
        repository = fetch_github_repository(
            "https://github.com/example/project",
            transport=httpx.MockTransport(api_response),
        )
        with (
            patch.object(projects, "fetch_github_repository", return_value=repository),
            patch.object(
                self.db[PROJECTS],
                "insert_one",
                side_effect=AutoReconnect("db failure"),
            ),
        ):
            with self.assertRaises(HTTPException) as error:
                projects.import_github_project(
                    GitHubImportRequest(github_url="https://github.com/example/project"),
                    Response(),
                    self.db,
                )
        self.assertEqual(error.exception.status_code, 500)
        self.assertEqual(self.db[PROJECTS].count_documents({}), 0)

    def test_project_review_requires_token_and_can_approve_with_verified_demo(self):
        project_id = self.db[PROJECTS].insert_one({
            "profile_id": str(self.profile_id),
            "name": "Imported repository",
            "github_url": "https://github.com/example/project",
            "source_type": "github",
            "status": "pending_review",
        }).inserted_id

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as disabled:
                projects.require_admin_token("admin-secret")
        self.assertEqual(disabled.exception.status_code, 503)

        with patch.dict(os.environ, {"ADMIN_API_TOKEN": "admin-secret"}):
            projects.require_admin_token("admin-secret")
            with self.assertRaises(HTTPException) as unauthorized:
                projects.require_admin_token("wrong-secret")
        self.assertEqual(unauthorized.exception.status_code, 401)

        approved = projects.review_project(
            str(project_id),
            ProjectReviewRequest(
                status="verified",
                deployed_url="https://demo.example",
                category="Full-stack projects",
            ),
            self.db,
        )
        self.assertEqual(approved["status"], "verified")
        self.assertEqual(approved["deployed_url"], "https://demo.example")

    def test_category_classifier_uses_project_metadata(self):
        self.assertEqual(classify_project("React and HTML web interface"), "Frontend projects")
        self.assertEqual(classify_project("Python machine learning model"), "AI projects")
        self.assertEqual(classify_project("documentation and examples"), "Other projects")


if __name__ == "__main__":
    unittest.main()

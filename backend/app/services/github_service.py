import base64
import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


GITHUB_API_URL = "https://api.github.com"
MAX_API_RESPONSE_BYTES = 1_000_000
MAX_README_LENGTH = 4_000
API_TIMEOUT = httpx.Timeout(8.0, connect=3.0)


class GitHubImportError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass
class GitHubRepository:
    owner: str
    name: str
    description: str | None
    repository_url: str
    language: str | None
    topics: list[str]
    readme_summary: str | None
    category: str


def parse_repository_url(github_url: str) -> tuple[str, str, str]:
    parsed = urlsplit(github_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.port not in (None, 443)
    ):
        raise GitHubImportError(422, "Provide a public repository URL on https://github.com.")

    path_match = re.fullmatch(r"/([^/]+)/([^/]+)/?", parsed.path)
    if not path_match:
        raise GitHubImportError(422, "URL must point directly to /owner/repository.")

    owner, repository = path_match.groups()
    repository = repository.removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner):
        raise GitHubImportError(422, "The GitHub owner name is invalid.")
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", repository)
        or repository in {".", ".."}
    ):
        raise GitHubImportError(422, "The GitHub repository name is invalid.")

    return owner, repository, f"https://github.com/{owner}/{repository}"


def _read_limited_response(response: httpx.Response) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > MAX_API_RESPONSE_BYTES:
        raise GitHubImportError(502, "GitHub returned a response that was too large.")

    content = bytearray()
    for chunk in response.iter_bytes():
        content.extend(chunk)
        if len(content) > MAX_API_RESPONSE_BYTES:
            raise GitHubImportError(502, "GitHub returned a response that was too large.")
    return bytes(content)


def _get_json(client: httpx.Client, path: str, *, optional: bool = False):
    try:
        with client.stream("GET", path) as response:
            if response.status_code == 404 and optional:
                return None
            body = _read_limited_response(response)
            if response.status_code >= 400:
                if response.status_code == 404:
                    raise GitHubImportError(404, "The public GitHub repository was not found.")
                if response.status_code == 429 or (
                    response.status_code == 403
                    and response.headers.get("x-ratelimit-remaining") == "0"
                ):
                    raise GitHubImportError(429, "GitHub API rate limit reached. Try again later.")
                if response.status_code == 403:
                    raise GitHubImportError(404, "The repository is private or unavailable.")
                raise GitHubImportError(502, "GitHub could not provide repository metadata.")
            return json.loads(body)
    except GitHubImportError:
        raise
    except httpx.TimeoutException as exc:
        raise GitHubImportError(504, "GitHub request timed out. Try again later.") from exc
    except (httpx.RequestError, json.JSONDecodeError, ValueError) as exc:
        raise GitHubImportError(502, "Unable to read repository data from GitHub.") from exc


def _decode_readme(readme_data: dict | None) -> str | None:
    if not readme_data:
        return None
    encoded = readme_data.get("content")
    if not isinstance(encoded, str):
        return None
    try:
        decoded = base64.b64decode(encoded, validate=False).decode("utf-8", errors="replace")
    except (ValueError, UnicodeError):
        return None

    summary = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", decoded)
    summary = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", summary)
    summary = re.sub(r"<[^>]+>", " ", summary)
    summary = re.sub(r"```[\s\S]*?```", " ", summary)
    summary = re.sub(r"[#>*_`]", " ", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    return summary[:MAX_README_LENGTH] or None


def classify_project(text: str) -> str:
    value = text.casefold()
    if re.search(r"\b(ai|artificial intelligence|machine learning|deep learning|llm|pytorch|tensorflow|keras|computer vision|yolo|neural network)\b", value):
        return "AI projects"
    frontend = re.search(r"\b(react|next\.?js|vue|angular|svelte|frontend|html|css)\b", value)
    backend = re.search(r"\b(api|backend|server|database|express|fastapi|django|flask|mongodb|mysql|postgresql)\b", value)
    if frontend and backend:
        return "Full-stack projects"
    if frontend:
        return "Frontend projects"
    return "Other projects"


def fetch_github_repository(
    github_url: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> GitHubRepository:
    owner, repository, canonical_url = parse_repository_url(github_url)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Portfolio-Chatbot-Project-Importer",
    }
    try:
        with httpx.Client(
            base_url=GITHUB_API_URL,
            headers=headers,
            timeout=API_TIMEOUT,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        ) as client:
            metadata = _get_json(client, f"/repos/{owner}/{repository}")
            readme_data = _get_json(
                client,
                f"/repos/{owner}/{repository}/readme",
                optional=True,
            )
    except GitHubImportError:
        raise
    except httpx.TimeoutException as exc:
        raise GitHubImportError(504, "GitHub request timed out. Try again later.") from exc
    except httpx.RequestError as exc:
        raise GitHubImportError(502, "Unable to connect to GitHub.") from exc

    if not isinstance(metadata, dict):
        raise GitHubImportError(502, "GitHub returned invalid repository metadata.")
    name = metadata.get("name")
    if not isinstance(name, str) or not name:
        raise GitHubImportError(502, "GitHub returned invalid repository metadata.")

    if readme_data is not None and not isinstance(readme_data, dict):
        raise GitHubImportError(502, "GitHub returned invalid README metadata.")

    readme_summary = _decode_readme(readme_data)
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        description = readme_summary
    else:
        description = description.strip()
        if readme_summary:
            description = f"{description}\n\nREADME summary: {readme_summary}"

    language = metadata.get("language")
    topics = metadata.get("topics")
    topics = [topic for topic in topics if isinstance(topic, str)] if isinstance(topics, list) else []
    category = classify_project(
        " ".join([name, description or "", language or "", *topics, readme_summary or ""])
    )
    return GitHubRepository(
        owner=owner,
        name=name[:200],
        description=description,
        repository_url=canonical_url,
        language=language if isinstance(language, str) else None,
        topics=topics,
        readme_summary=readme_summary,
        category=category,
    )

from datetime import datetime, timezone
import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pymongo import DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database import get_db, parse_object_id, serialize_document
from app.models import PROFILES, PROJECTS
from app.schema import (
    GitHubImportRequest,
    GitHubImportResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectReviewRequest,
    ProjectUpdate,
)
from app.services.github_service import (
    GitHubImportError,
    GitHubRepository,
    fetch_github_repository,
    parse_repository_url,
)

router = APIRouter(
    prefix="/api/projects",
    tags=["Projects"],
)


def get_default_profile(db: Database) -> dict:
    profile = db[PROFILES].find_one(sort=[("_id", 1)])
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Create a profile before adding projects.",
        )
    return profile


def find_project(db: Database, profile_id: str, project_id: str) -> dict | None:
    object_id = parse_object_id(project_id)
    if object_id is None:
        return None
    return db[PROJECTS].find_one({
        "_id": object_id,
        "profile_id": profile_id,
    })


def require_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    configured_token = os.getenv("ADMIN_API_TOKEN")
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project review is disabled until ADMIN_API_TOKEN is configured.",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, configured_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-Admin-Token is required.",
        )


def serialize_github_import(project: dict, repository, import_status: str):
    project_data = serialize_document(project)
    project_data.update({
        "owner": repository.owner,
        "language": repository.language,
        "topics": repository.topics,
        "readme_summary": repository.readme_summary,
        "import_status": import_status,
    })
    return GitHubImportResponse.model_validate(project_data)


def existing_repository_response(profile_id: str, canonical_url: str, owner: str, db: Database):
    existing = db[PROJECTS].find_one({
        "profile_id": profile_id,
        "github_url": canonical_url,
    })
    if not existing:
        return None
    repository = GitHubRepository(
        owner=owner,
        name=existing["name"],
        description=existing.get("description"),
        repository_url=canonical_url,
        language=(existing.get("technologies") or [None])[0],
        topics=[],
        readme_summary=None,
        category=existing.get("category") or "Other projects",
    )
    return serialize_github_import(existing, repository, "already_exists")


@router.post(
    "/import-github",
    response_model=GitHubImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_github_project(
    request: GitHubImportRequest,
    response: Response,
    db: Database = Depends(get_db),
):
    try:
        owner, _, canonical_url = parse_repository_url(request.github_url)
    except GitHubImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    profile_id = str(get_default_profile(db)["_id"])
    existing = existing_repository_response(profile_id, canonical_url, owner, db)
    if existing:
        response.status_code = status.HTTP_200_OK
        return existing

    try:
        repository = fetch_github_repository(canonical_url)
    except GitHubImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    now = datetime.now(timezone.utc)
    document = {
        "profile_id": profile_id,
        "name": repository.name,
        "description": repository.description,
        "role": None,
        "contributions": None,
        "outcomes": None,
        "technologies": list(dict.fromkeys(
            ([repository.language] if repository.language else [])
            + repository.topics
        )),
        "category": repository.category,
        "github_url": repository.repository_url,
        "deployed_url": None,
        "source_type": "github",
        "evidence_source": repository.repository_url,
        "status": "pending_review",
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = db[PROJECTS].insert_one(document)
        project = db[PROJECTS].find_one({"_id": result.inserted_id})
        return serialize_github_import(project, repository, "imported")
    except DuplicateKeyError:
        existing = existing_repository_response(profile_id, canonical_url, owner, db)
        if existing:
            response.status_code = status.HTTP_200_OK
            return existing
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the imported GitHub project.",
        )
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the imported GitHub project.",
        ) from exc


@router.get(
    "/review",
    response_model=list[ProjectResponse],
    dependencies=[Depends(require_admin_token)],
)
def get_projects_awaiting_review(db: Database = Depends(get_db)):
    profile_id = str(get_default_profile(db)["_id"])
    return [
        serialize_document(project)
        for project in db[PROJECTS].find({
            "profile_id": profile_id,
            "status": "pending_review",
        }).sort("_id", DESCENDING)
    ]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    project_data: ProjectCreate,
    db: Database = Depends(get_db),
):
    profile_id = str(get_default_profile(db)["_id"])
    now = datetime.now(timezone.utc)
    document = project_data.model_dump()
    document.update({
        "profile_id": profile_id,
        "status": "pending_review",
        "source_type": "manual",
        "evidence_source": None,
        "created_at": now,
        "updated_at": now,
    })
    result = db[PROJECTS].insert_one(document)
    return serialize_document(db[PROJECTS].find_one({"_id": result.inserted_id}))


@router.get("", response_model=list[ProjectResponse])
def get_projects(db: Database = Depends(get_db)):
    profile_id = str(get_default_profile(db)["_id"])
    return [
        serialize_document(project)
        for project in db[PROJECTS].find({"profile_id": profile_id}).sort(
            "_id", DESCENDING
        )
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Database = Depends(get_db)):
    profile_id = str(get_default_profile(db)["_id"])
    project = find_project(db, profile_id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return serialize_document(project)


@router.patch(
    "/{project_id}/review",
    response_model=ProjectResponse,
    dependencies=[Depends(require_admin_token)],
)
def review_project(
    project_id: str,
    review_data: ProjectReviewRequest,
    db: Database = Depends(get_db),
):
    profile_id = str(get_default_profile(db)["_id"])
    project = find_project(db, profile_id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("status") != "pending_review":
        raise HTTPException(
            status_code=409,
            detail="Only pending projects can be reviewed.",
        )

    updates = review_data.model_dump(exclude_unset=True)
    updates["updated_at"] = datetime.now(timezone.utc)
    try:
        updated_project = db[PROJECTS].find_one_and_update(
            {
                "_id": project["_id"],
                "profile_id": profile_id,
                "status": "pending_review",
            },
            {"$set": updates},
            return_document=True,
        )
    except PyMongoError as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to save the project review.",
        ) from exc
    if not updated_project:
        raise HTTPException(
            status_code=409,
            detail="Only pending projects can be reviewed.",
        )
    return serialize_document(updated_project)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: Database = Depends(get_db),
):
    profile_id = str(get_default_profile(db)["_id"])
    project = find_project(db, profile_id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = project_data.model_dump(exclude_unset=True)
    if updates.get("name") is not None and not updates["name"].strip():
        raise HTTPException(status_code=422, detail="Project name cannot be empty")
    if updates:
        updates.update({
            "status": "pending_review",
            "updated_at": datetime.now(timezone.utc),
        })
        project = db[PROJECTS].find_one_and_update(
            {"_id": project["_id"], "profile_id": profile_id},
            {"$set": updates},
            return_document=True,
        )
    return serialize_document(project)


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Database = Depends(get_db)):
    profile_id = str(get_default_profile(db)["_id"])
    object_id = parse_object_id(project_id)
    result = (
        db[PROJECTS].delete_one({
            "_id": object_id,
            "profile_id": profile_id,
        })
        if object_id
        else None
    )
    if not result or not result.deleted_count:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted successfully"}

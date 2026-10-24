
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Header, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Profile, Project
from app.schema import (
    GitHubImportRequest,
    GitHubImportResponse,
    ProjectCreate,
    ProjectReviewRequest,
    ProjectUpdate,
    ProjectResponse,
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


def get_default_profile(db: Session) -> Profile:
    profile = db.query(Profile).order_by(Profile.id).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Create a profile before adding projects.",
        )

    return profile


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


def serialize_github_import(project: Project, repository, import_status: str):
    project_data = ProjectResponse.model_validate(project).model_dump()
    project_data.update({
        "owner": repository.owner,
        "language": repository.language,
        "topics": repository.topics,
        "readme_summary": repository.readme_summary,
        "import_status": import_status,
    })
    return GitHubImportResponse.model_validate(project_data)


@router.post(
    "/import-github",
    response_model=GitHubImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_github_project(
    request: GitHubImportRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        owner, _, canonical_url = parse_repository_url(request.github_url)
    except GitHubImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    profile = get_default_profile(db)
    existing = (
        db.query(Project)
        .filter(
            Project.profile_id == profile.id,
            Project.github_url == canonical_url,
        )
        .first()
    )
    if existing:
        response.status_code = status.HTTP_200_OK
        repository = GitHubRepository(
            owner=owner,
            name=existing.name,
            description=existing.description,
            repository_url=canonical_url,
            language=(existing.technologies or [None])[0],
            topics=[],
            readme_summary=None,
            category=existing.category or "Other projects",
        )
        return serialize_github_import(existing, repository, "already_exists")

    try:
        repository = fetch_github_repository(canonical_url)
        project = Project(
            profile_id=profile.id,
            name=repository.name,
            description=repository.description,
            technologies=list(dict.fromkeys(
                ([repository.language] if repository.language else [])
                + repository.topics
            )),
            category=repository.category,
            github_url=repository.repository_url,
            source_type="github",
            evidence_source=repository.repository_url,
            status="pending_review",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return serialize_github_import(project, repository, "imported")
    except GitHubImportError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except IntegrityError as exc:
        db.rollback()
        existing = (
            db.query(Project)
            .filter(
                Project.profile_id == profile.id,
                Project.github_url == canonical_url,
            )
            .first()
        )
        if existing:
            response.status_code = status.HTTP_200_OK
            existing_repository = GitHubRepository(
                owner=owner,
                name=existing.name,
                description=existing.description,
                repository_url=canonical_url,
                language=(existing.technologies or [None])[0],
                topics=[],
                readme_summary=None,
                category=existing.category or "Other projects",
            )
            return serialize_github_import(
                existing,
                existing_repository,
                "already_exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the imported GitHub project.",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the imported GitHub project.",
        ) from exc


@router.get(
    "/review",
    response_model=list[ProjectResponse],
    dependencies=[Depends(require_admin_token)],
)
def get_projects_awaiting_review(db: Session = Depends(get_db)):
    profile = get_default_profile(db)
    return (
        db.query(Project)
        .filter(
            Project.profile_id == profile.id,
            Project.status == "pending_review",
        )
        .order_by(Project.id.desc())
        .all()
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    project = Project(
        profile_id=profile.id,
        name=project_data.name,
        description=project_data.description,
        role=project_data.role,
        contributions=project_data.contributions,
        outcomes=project_data.outcomes,
        technologies=project_data.technologies,
        category=project_data.category,
        github_url=project_data.github_url,
        deployed_url=project_data.deployed_url,
        status="pending_review",
        source_type="manual",
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return project


@router.get("", response_model=list[ProjectResponse])
def get_projects(db: Session = Depends(get_db)):
    profile = get_default_profile(db)

    return (
        db.query(Project)
        .filter(Project.profile_id == profile.id)
        .order_by(Project.id.desc())
        .all()
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.profile_id == profile.id,
        )
        .first()
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.patch(
    "/{project_id}/review",
    response_model=ProjectResponse,
    dependencies=[Depends(require_admin_token)],
)
def review_project(
    project_id: int,
    review_data: ProjectReviewRequest,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.profile_id == profile.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != "pending_review":
        raise HTTPException(status_code=409, detail="Only pending projects can be reviewed.")

    updates = review_data.model_dump(exclude_unset=True, exclude={"status"})
    for field, value in updates.items():
        setattr(project, field, value)
    project.status = review_data.status

    try:
        db.commit()
        db.refresh(project)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save the project review.",
        ) from exc
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.profile_id == profile.id,
        )
        .first()
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = project_data.model_dump(exclude_unset=True)

    # Do not allow an empty project name.
    if updates.get("name") is not None and not updates["name"].strip():
        raise HTTPException(status_code=422, detail="Project name cannot be empty")

    # Editing a project invalidates its previous verification.
    if updates:
        for field, value in updates.items():
            setattr(project, field, value)

        project.status = "pending_review"

    db.commit()
    db.refresh(project)

    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.profile_id == profile.id,
        )
        .first()
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()

    return {"message": "Project deleted successfully"}

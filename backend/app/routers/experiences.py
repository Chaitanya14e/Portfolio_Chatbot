
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Profile, Experience
from app.schema import (
    ExperienceCreate,
    ExperienceUpdate,
    ExperienceResponse,
)

router = APIRouter(
    prefix="/api/experiences",
    tags=["Experience"],
)


def get_default_profile(db: Session) -> Profile:
    profile = db.query(Profile).order_by(Profile.id).first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Create a profile before adding experience.",
        )

    return profile


@router.post(
    "",
    response_model=ExperienceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_experience(
    data: ExperienceCreate,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    organization = data.organization.strip()
    role = data.role.strip()

    if not organization or not role:
        raise HTTPException(
            status_code=422,
            detail="Organization and role cannot be empty.",
        )

    experience = Experience(
        profile_id=profile.id,
        organization=organization,
        role=role,
        description=data.description,
        start_date=data.start_date,
        end_date=data.end_date,
        is_current=1 if data.is_current else 0,
        status="pending_review",
    )

    db.add(experience)
    db.commit()
    db.refresh(experience)

    return experience


@router.get("", response_model=list[ExperienceResponse])
def get_experiences(db: Session = Depends(get_db)):
    profile = get_default_profile(db)

    return (
        db.query(Experience)
        .filter(Experience.profile_id == profile.id)
        .order_by(Experience.id.desc())
        .all()
    )


@router.get("/{experience_id}", response_model=ExperienceResponse)
def get_experience(
    experience_id: int,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    experience = (
        db.query(Experience)
        .filter(
            Experience.id == experience_id,
            Experience.profile_id == profile.id,
        )
        .first()
    )

    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    return experience


@router.patch("/{experience_id}", response_model=ExperienceResponse)
def update_experience(
    experience_id: int,
    data: ExperienceUpdate,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    experience = (
        db.query(Experience)
        .filter(
            Experience.id == experience_id,
            Experience.profile_id == profile.id,
        )
        .first()
    )

    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    updates = data.model_dump(exclude_unset=True)

    for field in ("organization", "role"):
        if field in updates and updates[field] is not None:
            updates[field] = updates[field].strip()
            if not updates[field]:
                raise HTTPException(
                    status_code=422,
                    detail=f"{field} cannot be empty.",
                )

    if "is_current" in updates and updates["is_current"] is not None:
        updates["is_current"] = 1 if updates["is_current"] else 0

    if updates:
        for field, value in updates.items():
            setattr(experience, field, value)

        experience.status = "pending_review"

    db.commit()
    db.refresh(experience)

    return experience


@router.delete("/{experience_id}")
def delete_experience(
    experience_id: int,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    experience = (
        db.query(Experience)
        .filter(
            Experience.id == experience_id,
            Experience.profile_id == profile.id,
        )
        .first()
    )

    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    db.delete(experience)
    db.commit()

    return {"message": "Experience deleted successfully"}

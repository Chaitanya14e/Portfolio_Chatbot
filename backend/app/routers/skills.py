
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Profile, Skill
from app.schema import SkillCreate, SkillUpdate, SkillResponse

router = APIRouter(
    prefix="/api/skills",
    tags=["Skills"],
)


def get_default_profile(db: Session) -> Profile:
    profile = db.query(Profile).order_by(Profile.id).first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Create a profile before adding skills.",
        )

    return profile


@router.post(
    "",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_skill(
    skill_data: SkillCreate,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    skill = Skill(
        profile_id=profile.id,
        skill_name=skill_data.skill_name.strip(),
        category=skill_data.category,
        proficiency=skill_data.proficiency,
        status="pending_review",
    )

    if not skill.skill_name:
        raise HTTPException(
            status_code=422,
            detail="Skill name cannot be empty.",
        )

    db.add(skill)
    db.commit()
    db.refresh(skill)

    return skill


@router.get("", response_model=list[SkillResponse])
def get_skills(db: Session = Depends(get_db)):
    profile = get_default_profile(db)

    return (
        db.query(Skill)
        .filter(Skill.profile_id == profile.id)
        .order_by(Skill.id.desc())
        .all()
    )


@router.get("/{skill_id}", response_model=SkillResponse)
def get_skill(
    skill_id: int,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    skill = (
        db.query(Skill)
        .filter(
            Skill.id == skill_id,
            Skill.profile_id == profile.id,
        )
        .first()
    )

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return skill


@router.patch("/{skill_id}", response_model=SkillResponse)
def update_skill(
    skill_id: int,
    skill_data: SkillUpdate,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    skill = (
        db.query(Skill)
        .filter(
            Skill.id == skill_id,
            Skill.profile_id == profile.id,
        )
        .first()
    )

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    updates = skill_data.model_dump(exclude_unset=True)

    if updates.get("skill_name") is not None:
        updates["skill_name"] = updates["skill_name"].strip()

        if not updates["skill_name"]:
            raise HTTPException(
                status_code=422,
                detail="Skill name cannot be empty.",
            )

    if updates:
        for field, value in updates.items():
            setattr(skill, field, value)

        # Any change requires review again.
        skill.status = "pending_review"

    db.commit()
    db.refresh(skill)

    return skill


@router.delete("/{skill_id}")
def delete_skill(
    skill_id: int,
    db: Session = Depends(get_db),
):
    profile = get_default_profile(db)

    skill = (
        db.query(Skill)
        .filter(
            Skill.id == skill_id,
            Skill.profile_id == profile.id,
        )
        .first()
    )

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    db.delete(skill)
    db.commit()

    return {"message": "Skill deleted successfully"}

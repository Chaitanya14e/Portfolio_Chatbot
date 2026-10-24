from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import DESCENDING
from pymongo.database import Database

from app.database import get_db, parse_object_id, serialize_document
from app.models import PROFILES, SKILLS
from app.schema import SkillCreate, SkillResponse, SkillUpdate

router = APIRouter(
    prefix="/api/skills",
    tags=["Skills"],
)


def get_default_profile(db: Database) -> dict:
    profile = db[PROFILES].find_one(sort=[("_id", 1)])
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
    db: Database = Depends(get_db),
):
    profile = get_default_profile(db)
    skill_name = skill_data.skill_name.strip()
    if not skill_name:
        raise HTTPException(status_code=422, detail="Skill name cannot be empty.")

    document = skill_data.model_dump()
    document.update({
        "profile_id": str(profile["_id"]),
        "skill_name": skill_name,
        "status": "pending_review",
        "created_at": datetime.now(timezone.utc),
    })
    result = db[SKILLS].insert_one(document)
    return serialize_document(db[SKILLS].find_one({"_id": result.inserted_id}))


@router.get("", response_model=list[SkillResponse])
def get_skills(db: Database = Depends(get_db)):
    profile = get_default_profile(db)
    return [
        serialize_document(skill)
        for skill in db[SKILLS].find({"profile_id": str(profile["_id"])}).sort(
            "_id", DESCENDING
        )
    ]


@router.get("/{skill_id}", response_model=SkillResponse)
def get_skill(skill_id: str, db: Database = Depends(get_db)):
    profile = get_default_profile(db)
    object_id = parse_object_id(skill_id)
    skill = (
        db[SKILLS].find_one({
            "_id": object_id,
            "profile_id": str(profile["_id"]),
        })
        if object_id
        else None
    )
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return serialize_document(skill)


@router.patch("/{skill_id}", response_model=SkillResponse)
def update_skill(
    skill_id: str,
    skill_data: SkillUpdate,
    db: Database = Depends(get_db),
):
    profile = get_default_profile(db)
    object_id = parse_object_id(skill_id)
    if object_id is None:
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
        updates["status"] = "pending_review"
        skill = db[SKILLS].find_one_and_update(
            {"_id": object_id, "profile_id": str(profile["_id"])},
            {"$set": updates},
            return_document=True,
        )
    else:
        skill = db[SKILLS].find_one({
            "_id": object_id,
            "profile_id": str(profile["_id"]),
        })

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return serialize_document(skill)


@router.delete("/{skill_id}")
def delete_skill(skill_id: str, db: Database = Depends(get_db)):
    profile = get_default_profile(db)
    object_id = parse_object_id(skill_id)
    result = (
        db[SKILLS].delete_one({
            "_id": object_id,
            "profile_id": str(profile["_id"]),
        })
        if object_id
        else None
    )
    if not result or not result.deleted_count:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"message": "Skill deleted successfully"}

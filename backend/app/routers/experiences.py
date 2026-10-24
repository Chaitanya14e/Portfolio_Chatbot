from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import DESCENDING
from pymongo.database import Database

from app.database import get_db, parse_object_id, serialize_document
from app.models import EXPERIENCES, PROFILES
from app.schema import ExperienceCreate, ExperienceResponse, ExperienceUpdate

router = APIRouter(
    prefix="/api/experiences",
    tags=["Experience"],
)


def get_default_profile(db: Database) -> dict:
    profile = db[PROFILES].find_one(sort=[("_id", 1)])
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
    db: Database = Depends(get_db),
):
    profile = get_default_profile(db)
    organization = data.organization.strip()
    role = data.role.strip()
    if not organization or not role:
        raise HTTPException(
            status_code=422,
            detail="Organization and role cannot be empty.",
        )

    document = data.model_dump()
    document.update({
        "profile_id": str(profile["_id"]),
        "organization": organization,
        "role": role,
        "status": "pending_review",
        "created_at": datetime.now(timezone.utc),
    })
    result = db[EXPERIENCES].insert_one(document)
    return serialize_document(
        db[EXPERIENCES].find_one({"_id": result.inserted_id})
    )


@router.get("", response_model=list[ExperienceResponse])
def get_experiences(db: Database = Depends(get_db)):
    profile = get_default_profile(db)
    return [
        serialize_document(experience)
        for experience in db[EXPERIENCES]
        .find({"profile_id": str(profile["_id"])})
        .sort("_id", DESCENDING)
    ]


@router.get("/{experience_id}", response_model=ExperienceResponse)
def get_experience(experience_id: str, db: Database = Depends(get_db)):
    profile = get_default_profile(db)
    object_id = parse_object_id(experience_id)
    experience = (
        db[EXPERIENCES].find_one({
            "_id": object_id,
            "profile_id": str(profile["_id"]),
        })
        if object_id
        else None
    )
    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")
    return serialize_document(experience)


@router.patch("/{experience_id}", response_model=ExperienceResponse)
def update_experience(
    experience_id: str,
    data: ExperienceUpdate,
    db: Database = Depends(get_db),
):
    profile = get_default_profile(db)
    object_id = parse_object_id(experience_id)
    if object_id is None:
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

    if updates:
        updates["status"] = "pending_review"
        experience = db[EXPERIENCES].find_one_and_update(
            {"_id": object_id, "profile_id": str(profile["_id"])},
            {"$set": updates},
            return_document=True,
        )
    else:
        experience = db[EXPERIENCES].find_one({
            "_id": object_id,
            "profile_id": str(profile["_id"]),
        })

    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")
    return serialize_document(experience)


@router.delete("/{experience_id}")
def delete_experience(experience_id: str, db: Database = Depends(get_db)):
    profile = get_default_profile(db)
    object_id = parse_object_id(experience_id)
    result = (
        db[EXPERIENCES].delete_one({
            "_id": object_id,
            "profile_id": str(profile["_id"]),
        })
        if object_id
        else None
    )
    if not result or not result.deleted_count:
        raise HTTPException(status_code=404, detail="Experience not found")
    return {"message": "Experience deleted successfully"}

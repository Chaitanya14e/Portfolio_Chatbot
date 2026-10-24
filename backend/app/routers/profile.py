from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from app.database import get_db, parse_object_id, serialize_document
from app.models import PROFILES
from app.schema import ProfileCreate, ProfileResponse, ProfileUpdate

router = APIRouter(
    prefix="/api/profile",
    tags=["Profile"],
)


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    profile_data: ProfileCreate,
    db: Database = Depends(get_db),
):
    profiles = db[PROFILES]
    if profiles.find_one({}, {"_id": 1}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile already exists. Update the existing profile.",
        )

    now = datetime.now(timezone.utc)
    document = profile_data.model_dump()
    document.update({"created_at": now, "updated_at": now})
    result = profiles.insert_one(document)
    return serialize_document(profiles.find_one({"_id": result.inserted_id}))


@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(
    profile_id: str,
    db: Database = Depends(get_db),
):
    object_id = parse_object_id(profile_id)
    profile = db[PROFILES].find_one({"_id": object_id}) if object_id else None
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return serialize_document(profile)


@router.patch("/{profile_id}", response_model=ProfileResponse)
def update_profile(
    profile_id: str,
    profile_data: ProfileUpdate,
    db: Database = Depends(get_db),
):
    object_id = parse_object_id(profile_id)
    if object_id is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    updates = profile_data.model_dump(exclude_unset=True)
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        profile = db[PROFILES].find_one_and_update(
            {"_id": object_id},
            {"$set": updates},
            return_document=True,
        )
    else:
        profile = db[PROFILES].find_one({"_id": object_id})

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return serialize_document(profile)

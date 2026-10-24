
import json
import re
from datetime import datetime, timezone

from pymongo.database import Database

from app.models import PROFILE_FACTS, PROFILES


def make_fact_key(value: str) -> str:
    """Create a consistent key for a fact."""
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:100]


def save_extracted_facts(
    db: Database,
    extracted: dict,
    evidence_source: str,
) -> dict:
    """
    Save extracted resume facts for the existing profile.
    New or updated facts remain unverified until reviewed.
    """

    profile = db[PROFILES].find_one(sort=[("_id", 1)])

    if profile is None:
        raise ValueError(
            "No profile exists. Create a profile before importing resume facts."
        )

    candidates = []

    def add_fact(key: str, value, notes=None):
        if value is None or value == "" or value == []:
            return

        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)

        candidates.append({
            "fact_key": key[:150],
            "fact_value": value,
            "notes": notes,
        })

    # Basic profile information
    add_fact("name", extracted.get("name"))
    add_fact("headline", extracted.get("headline"))
    add_fact("summary", extracted.get("summary"))

    # Education, achievements, and interests
    for item in extracted.get("education", []):
        add_fact(
            f"education_{make_fact_key(item)}",
            item,
        )

    for item in extracted.get("achievements", []):
        add_fact(
            f"achievement_{make_fact_key(item)}",
            item,
        )

    for item in extracted.get("areas_of_interest", []):
        add_fact(
            f"interest_{make_fact_key(item)}",
            item,
        )

    # Skills: expand grouped section headings into individual skills.
    for skill in extracted.get("skills", []):
        skill_name = skill.get("skill_name", "").strip()
        category = skill.get("category")
        evidence = skill.get("evidence")

        if not skill_name:
            continue

        if (
            category
            and skill_name.casefold() == category.casefold()
            and evidence
        ):
            for individual_skill in evidence.split(","):
                individual_skill = individual_skill.strip()
                if individual_skill:
                    add_fact(
                        f"skill_{make_fact_key(individual_skill)}",
                        {
                            "name": individual_skill,
                            "category": category,
                            "proficiency": None,
                        },
                        notes=f"Resume evidence: {evidence}",
                    )
        else:
            add_fact(
                f"skill_{make_fact_key(skill_name)}",
                {
                    "name": skill_name,
                    "category": category,
                    "proficiency": skill.get("proficiency"),
                },
                notes=f"Resume evidence: {evidence or 'Not provided'}",
            )

    # Projects
    for project in extracted.get("projects", []):
        name = project.get("name", "").strip()

        if not name:
            continue

        add_fact(
            f"project_{make_fact_key(name)}",
            project,
            notes=f"Resume evidence: {project.get('evidence') or 'Not provided'}",
        )

    # Experiences
    for experience in extracted.get("experiences", []):
        organization = experience.get("organization", "").strip()
        role = experience.get("role", "").strip()

        if not organization or not role:
            continue

        key = (
            f"experience_{make_fact_key(organization)}_"
            f"{make_fact_key(role)}"
        )

        add_fact(key, experience)

    inserted = 0
    updated = 0
    facts = db[PROFILE_FACTS]
    profile_id = str(profile["_id"])
    for candidate in candidates:
        result = facts.update_one(
            {
                "profile_id": profile_id,
                "fact_key": candidate["fact_key"],
            },
            {
                "$set": {
                    "fact_value": candidate["fact_value"],
                    "evidence_source": evidence_source,
                    "notes": candidate["notes"],
                    "status": "unverified",
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "profile_id": profile_id,
                    "fact_key": candidate["fact_key"],
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        else:
            updated += 1

    return {
        "profile_id": profile_id,
        "inserted": inserted,
        "updated": updated,
        "total_processed": len(candidates),
        "status": "unverified",
    }

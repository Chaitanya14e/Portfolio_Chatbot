
import json
import re

from sqlalchemy.orm import Session

from app.models import Profile, ProfileFact


def make_fact_key(value: str) -> str:
    """Create a consistent key for a fact."""
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:100]


def save_extracted_facts(
    db: Session,
    extracted: dict,
    evidence_source: str,
) -> dict:
    """
    Save extracted resume facts for the existing profile.
    New or updated facts remain unverified until reviewed.
    """

    profile = db.query(Profile).order_by(Profile.id).first()

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

    try:
        for candidate in candidates:
            existing = (
                db.query(ProfileFact)
                .filter(
                    ProfileFact.profile_id == profile.id,
                    ProfileFact.fact_key == candidate["fact_key"],
                )
                .first()
            )

            if existing:
                existing.fact_value = candidate["fact_value"]
                existing.evidence_source = evidence_source
                existing.notes = candidate["notes"]
                existing.status = "unverified"
                updated += 1
            else:
                db.add(
                    ProfileFact(
                        profile_id=profile.id,
                        fact_key=candidate["fact_key"],
                        fact_value=candidate["fact_value"],
                        status="unverified",
                        evidence_source=evidence_source,
                        notes=candidate["notes"],
                    )
                )
                inserted += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "profile_id": profile.id,
        "inserted": inserted,
        "updated": updated,
        "total_processed": len(candidates),
        "status": "unverified",
    }

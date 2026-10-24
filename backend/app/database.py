import os
from pathlib import Path
from typing import Generator

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import ServerSelectionTimeoutError

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
IS_RENDER = os.getenv("RENDER", "").lower() == "true"
if not MONGODB_URI:
    if IS_RENDER:
        raise RuntimeError(
            "MONGODB_URI is not configured. Add your MongoDB connection string "
            "to the Render service's Environment settings."
        )
    MONGODB_URI = "mongodb://localhost:27017"

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
database_name = os.getenv("MONGODB_DATABASE")
database: Database = (
    client[database_name]
    if database_name
    else client.get_default_database(default="portfolio_chatbot")
)


def initialize_database() -> None:
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError as exc:
        raise RuntimeError(
            "Could not connect to MongoDB. Verify MONGODB_URI in the Render "
            "service's Environment settings and allow the service to connect "
            "in MongoDB Atlas Network Access."
        ) from exc

    database["projects"].create_index(
        [("profile_id", ASCENDING), ("github_url", ASCENDING)],
        unique=True,
        partialFilterExpression={"github_url": {"$type": "string"}},
        name="uq_projects_profile_github_url",
    )
    database["profile_facts"].create_index(
        [("profile_id", ASCENDING), ("fact_key", ASCENDING)],
        unique=True,
        name="uq_profile_facts_profile_fact_key",
    )


def get_db() -> Generator[Database, None, None]:
    yield database


def serialize_document(document: dict | None) -> dict | None:
    if document is None:
        return None

    result = dict(document)
    result["id"] = str(result.pop("_id"))
    return result


def parse_object_id(value: str) -> ObjectId | None:
    if not ObjectId.is_valid(value):
        return None
    return ObjectId(value)

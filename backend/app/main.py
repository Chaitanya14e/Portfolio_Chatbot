from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from app.database import database, initialize_database
from app.routers import profile
from app.routers import projects
from app.routers import skills
from app.routers import experiences
from app.routers import resume
from app.routers import chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Personal Portfolio Chatbot API",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(projects.router)
app.include_router(skills.router)
app.include_router(experiences.router)
app.include_router(resume.router)
app.include_router(chat.router)

@app.get("/")
def root():
    return {
        "message": "Personal Portfolio Chatbot API is running",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/db-health")
def database_health_check():
    try:
        database.command("ping")
        return {
            "status": "connected",
            "database": database.name,
        }
    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed. Check MongoDB and configuration.",
        ) from exc

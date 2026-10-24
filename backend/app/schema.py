
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

ProjectCategory = Literal[
    "Frontend projects",
    "Full-stack projects",
    "AI projects",
    "Other projects",
]


def is_github_repository_path(path: str) -> bool:
    path_match = re.fullmatch(r"/([^/]+)/([^/]+)/?", path)
    owner_pattern = re.compile(
        r"(?=.{1,39}\Z)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\Z"
    )
    repository_pattern = re.compile(r"(?=.{1,100}\Z)[A-Za-z0-9][A-Za-z0-9._-]*\Z")
    return bool(
        path_match
        and owner_pattern.fullmatch(path_match.group(1))
        and repository_pattern.fullmatch(path_match.group(2).removesuffix(".git"))
    )


def validate_https_url(value: str | None, hostname: str | None = None) -> str | None:
    if value is None:
        return value
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or (hostname and parsed.hostname != hostname)
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        expected_host = f" on {hostname}" if hostname else ""
        raise ValueError(f"Project URL must be a valid HTTPS URL{expected_host}.")
    if hostname == "github.com" and not is_github_repository_path(parsed.path):
        raise ValueError("GitHub URLs must point directly to /owner/repository.")
    return value


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None


class ProfileResponse(ProfileCreate):
    id: str

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    role: str | None = None
    contributions: str | None = None
    outcomes: str | None = None
    technologies: list[str] = Field(default_factory=list)
    category: ProjectCategory | None = None
    github_url: str | None = Field(default=None, max_length=500)
    deployed_url: str | None = Field(default=None, max_length=500)

    @field_validator("github_url")
    @classmethod
    def validate_github_project_url(cls, value: str | None) -> str | None:
        return validate_https_url(value, hostname="github.com")

    @field_validator("deployed_url")
    @classmethod
    def validate_deployed_project_url(cls, value: str | None) -> str | None:
        return validate_https_url(value)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    role: str | None = None
    contributions: str | None = None
    outcomes: str | None = None
    technologies: list[str] | None = None
    category: ProjectCategory | None = None
    github_url: str | None = Field(default=None, max_length=500)
    deployed_url: str | None = Field(default=None, max_length=500)

    @field_validator("github_url")
    @classmethod
    def validate_github_project_url(cls, value: str | None) -> str | None:
        return validate_https_url(value, hostname="github.com")

    @field_validator("deployed_url")
    @classmethod
    def validate_deployed_project_url(cls, value: str | None) -> str | None:
        return validate_https_url(value)


class ProjectResponse(ProjectCreate):
    id: str
    profile_id: str
    status: str
    evidence_source: str | None = None
    source_type: str = "manual"

    @field_validator("technologies", mode="before")
    @classmethod
    def normalize_missing_technologies(cls, value):
        return value or []



class GitHubImportRequest(BaseModel):
    github_url: str = Field(min_length=1, max_length=500)

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Provide a public repository URL on https://github.com.")

        if not is_github_repository_path(parsed.path):
            raise ValueError("URL must point directly to /owner/repository.")
        return value


class GitHubImportResponse(ProjectResponse):
    owner: str
    language: str | None = None
    topics: list[str] = Field(default_factory=list)
    readme_summary: str | None = None
    import_status: Literal["imported", "already_exists"]


class ProjectReviewRequest(BaseModel):
    status: Literal["verified", "rejected"]
    description: str | None = None
    role: str | None = None
    contributions: str | None = None
    outcomes: str | None = None
    technologies: list[str] | None = None
    category: ProjectCategory | None = None
    deployed_url: str | None = Field(default=None, max_length=500)

    @field_validator("deployed_url")
    @classmethod
    def validate_deployed_project_url(cls, value: str | None) -> str | None:
        return validate_https_url(value)


class SkillCreate(BaseModel):
    skill_name: str = Field(min_length=1, max_length=150)
    category: str | None = None
    proficiency: str | None = None


class SkillUpdate(BaseModel):
    skill_name: str | None = Field(default=None, min_length=1, max_length=150)
    category: str | None = None
    proficiency: str | None = None


class SkillResponse(SkillCreate):
    id: str
    profile_id: str
    status: str
    evidence_source: str | None = None



class ExperienceCreate(BaseModel):
    organization: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=150)
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False


class ExperienceUpdate(BaseModel):
    organization: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool | None = None


class ExperienceResponse(ExperienceCreate):
    id: str
    profile_id: str
    status: str
    evidence_source: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str

    
class ResumeSkillFact(BaseModel):
    skill_name: str
    category: str | None = None
    proficiency: str | None = None
    evidence: str | None = None


class ResumeProjectFact(BaseModel):
    name: str
    description: str | None = None
    role: str | None = None
    contributions: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    evidence: str | None = None


class ResumeExperienceFact(BaseModel):
    organization: str
    role: str
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    evidence: str | None = None


class ResumeExtraction(BaseModel):
    name: str | None = None
    headline: str | None = None
    summary: str | None = None
    education: list[str] = Field(default_factory=list)
    skills: list[ResumeSkillFact] = Field(default_factory=list)
    projects: list[ResumeProjectFact] = Field(default_factory=list)
    experiences: list[ResumeExperienceFact] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    areas_of_interest: list[str] = Field(default_factory=list)

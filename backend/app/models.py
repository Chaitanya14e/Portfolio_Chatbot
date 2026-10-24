
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    headline = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    skills = relationship(
        "Skill", back_populates="profile", cascade="all, delete-orphan"
    )
    projects = relationship(
        "Project", back_populates="profile", cascade="all, delete-orphan"
    )
    experiences = relationship(
        "Experience", back_populates="profile", cascade="all, delete-orphan"
    )
    facts = relationship(
        "ProfileFact", back_populates="profile", cascade="all, delete-orphan"
    )


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    skill_name = Column(String(150), nullable=False)
    category = Column(String(100), nullable=True)
    proficiency = Column(String(50), nullable=True)

    # pending_review, verified, unknown, not_proficient, rejected
    status = Column(
        String(30), nullable=False, default="pending_review"
    )
    evidence_source = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="skills")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "github_url",
            name="uq_projects_profile_github_url",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    role = Column(String(150), nullable=True)
    contributions = Column(Text, nullable=True)
    outcomes = Column(Text, nullable=True)

    # Example: ["Python", "FastAPI", "MySQL"]
    technologies = Column(JSON, nullable=True)
    category = Column(String(50), nullable=True)
    github_url = Column(String(500), nullable=True)
    deployed_url = Column(String(500), nullable=True)
    source_type = Column(
        String(20),
        nullable=False,
        default="manual",
        server_default="manual",
    )

    # pending_review, verified, rejected
    status = Column(
        String(30), nullable=False, default="pending_review"
    )
    evidence_source = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    profile = relationship("Profile", back_populates="projects")


class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )
    organization = Column(String(200), nullable=False)
    role = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(String(30), nullable=True)
    end_date = Column(String(30), nullable=True)
    is_current = Column(Integer, nullable=False, default=0)

    # pending_review, verified, rejected
    status = Column(
        String(30), nullable=False, default="pending_review"
    )
    evidence_source = Column(String(255), nullable=True)

    profile = relationship("Profile", back_populates="experiences")


class ProfileFact(Base):
    __tablename__ = "profile_facts"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(
        Integer, ForeignKey("profiles.id"), nullable=False, index=True
    )

    # Examples: "hardware_knowledge", "python_proficiency"
    fact_key = Column(String(150), nullable=False)
    fact_value = Column(Text, nullable=True)

    # verified, unverified, unknown, not_proficient, rejected
    status = Column(
        String(30), nullable=False, default="unverified"
    )
    evidence_source = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    profile = relationship("Profile", back_populates="facts")

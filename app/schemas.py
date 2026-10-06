"""Pydantic request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import ApplicationStatus, TopicStatus, UserRole

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=120)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    program: str = Field(default="Ingeniería de Software", max_length=120)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: UserRole
    program: str


class TopicCreate(BaseModel):
    title: str = Field(min_length=10, max_length=200)
    description: str = Field(min_length=30)
    research_line: str = Field(min_length=3, max_length=120)
    program: str = Field(min_length=3, max_length=120)
    keywords: str = Field(default="", max_length=255)
    max_students: int = Field(default=1, ge=1, le=3)


class TopicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=10, max_length=200)
    description: str | None = Field(default=None, min_length=30)
    research_line: str | None = Field(default=None, min_length=3, max_length=120)
    program: str | None = Field(default=None, min_length=3, max_length=120)
    keywords: str | None = Field(default=None, max_length=255)
    max_students: int | None = Field(default=None, ge=1, le=3)


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    research_line: str
    program: str
    keywords: str
    max_students: int
    status: TopicStatus
    professor_id: int
    professor_name: str
    accepted_count: int
    pending_count: int
    created_at: datetime


class SimilarityRequest(BaseModel):
    title: str = Field(min_length=3)
    description: str = ""
    keywords: str = ""
    exclude_topic_id: int | None = None


class SimilarTopic(BaseModel):
    topic_id: int
    title: str
    status: TopicStatus
    professor_name: str
    score: float
    is_duplicate: bool


class TopicCreateResult(BaseModel):
    topic: TopicOut
    similar_topics: list[SimilarTopic]


class ApplicationCreate(BaseModel):
    topic_id: int
    motivation: str = Field(min_length=20, max_length=2000)


class ApplicationReview(BaseModel):
    decision: ApplicationStatus  # accepted | rejected
    feedback: str = Field(default="", max_length=2000)


class ApplicationOut(BaseModel):
    id: int
    topic_id: int
    topic_title: str
    student_id: int
    student_name: str
    student_email: str
    motivation: str
    status: ApplicationStatus
    feedback: str
    created_at: datetime
    reviewed_at: datetime | None

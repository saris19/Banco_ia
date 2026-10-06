"""ORM models for the thesis project bank."""
import enum
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class UserRole(str, enum.Enum):
    STUDENT = "student"
    PROFESSOR = "professor"
    ADMIN = "admin"


class TopicStatus(str, enum.Enum):
    AVAILABLE = "available"   # open for applications
    ASSIGNED = "assigned"     # all seats taken
    CLOSED = "closed"         # withdrawn by the professor


class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class MilestoneStatus(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    NEEDS_CHANGES = "needs_changes"


def utc_now() -> datetime:
    """Naive UTC timestamp (SQLite stores datetimes without timezone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.STUDENT)
    program: Mapped[str] = mapped_column(String(120), default="Ingeniería de Software")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    topics: Mapped[list["Topic"]] = relationship(back_populates="professor")
    applications: Mapped[list["Application"]] = relationship(back_populates="student")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    research_line: Mapped[str] = mapped_column(String(120))
    program: Mapped[str] = mapped_column(String(120))
    keywords: Mapped[str] = mapped_column(String(255), default="")
    max_students: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[TopicStatus] = mapped_column(Enum(TopicStatus), default=TopicStatus.AVAILABLE)
    professor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    professor: Mapped[User] = relationship(back_populates="topics")
    applications: Mapped[list["Application"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )

    @property
    def accepted_count(self) -> int:
        return sum(1 for app in self.applications if app.status == ApplicationStatus.ACCEPTED)

    @property
    def pending_count(self) -> int:
        return sum(1 for app in self.applications if app.status == ApplicationStatus.PENDING)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("topic_id", "student_id", name="uq_topic_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    motivation: Mapped[str] = mapped_column(Text)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.PENDING
    )
    feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    topic: Mapped[Topic] = relationship(back_populates="applications")
    student: Mapped[User] = relationship(back_populates="applications")
    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class Milestone(Base):
    """Progress milestone between student and advisor.

    The table is already part of the data model; its endpoints and UI are
    scheduled for the second half (50%) of the project.
    """

    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[MilestoneStatus] = mapped_column(
        Enum(MilestoneStatus), default=MilestoneStatus.PENDING
    )
    advisor_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    application: Mapped[Application] = relationship(back_populates="milestones")

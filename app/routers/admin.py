"""Administration endpoints: statistics and professor account management."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application, ApplicationStatus, Topic, TopicStatus, User, UserRole
from ..schemas import EMAIL_PATTERN, UserOut
from ..security import get_current_user, hash_password, require_roles

router = APIRouter(prefix="/api/admin", tags=["admin"])

admin_only = require_roles(UserRole.ADMIN)


class ProfessorCreate(BaseModel):
    full_name: str = Field(min_length=3, max_length=120)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    program: str = Field(default="Ingeniería de Software", max_length=120)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Bank-wide indicators (visible to every role on the home dashboard)."""

    def count_topics(topic_status: TopicStatus) -> int:
        return db.scalar(select(func.count(Topic.id)).where(Topic.status == topic_status)) or 0

    def count_applications(application_status: ApplicationStatus) -> int:
        return db.scalar(select(func.count(Application.id)).where(Application.status == application_status)) or 0

    by_line = db.execute(
        select(Topic.research_line, func.count(Topic.id))
        .where(Topic.status != TopicStatus.CLOSED)
        .group_by(Topic.research_line)
        .order_by(func.count(Topic.id).desc())
    ).all()

    return {
        "topics": {
            "available": count_topics(TopicStatus.AVAILABLE),
            "assigned": count_topics(TopicStatus.ASSIGNED),
            "closed": count_topics(TopicStatus.CLOSED),
        },
        "applications": {
            "pending": count_applications(ApplicationStatus.PENDING),
            "accepted": count_applications(ApplicationStatus.ACCEPTED),
            "rejected": count_applications(ApplicationStatus.REJECTED),
        },
        "professors": db.scalar(select(func.count(User.id)).where(User.role == UserRole.PROFESSOR)) or 0,
        "students": db.scalar(select(func.count(User.id)).where(User.role == UserRole.STUDENT)) or 0,
        "topics_by_research_line": [{"research_line": line, "count": count} for line, count in by_line],
    }


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return db.scalars(select(User).order_by(User.role, User.full_name)).all()


@router.post("/professors", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_professor(payload: ProfessorCreate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    email = payload.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo.")
    professor = User(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=UserRole.PROFESSOR,
        program=payload.program.strip(),
    )
    db.add(professor)
    db.commit()
    db.refresh(professor)
    return professor

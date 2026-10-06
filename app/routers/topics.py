"""Thesis topic endpoints: browse, search, publish, edit, close and duplicate detection."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ApplicationStatus, Topic, TopicStatus, User, UserRole
from ..schemas import (
    SimilarityRequest,
    SimilarTopic,
    TopicCreate,
    TopicCreateResult,
    TopicOut,
    TopicUpdate,
)
from ..security import get_current_user, require_roles
from ..serializers import topic_to_out
from ..similarity import BLOCKING_THRESHOLD, rank_similar, topic_text

router = APIRouter(prefix="/api/topics", tags=["topics"])

professor_or_admin = require_roles(UserRole.PROFESSOR, UserRole.ADMIN)


def find_similar_topics(
    db: Session, title: str, description: str, keywords: str, exclude_topic_id: int | None = None
) -> list[SimilarTopic]:
    """Compare a candidate idea with every non-closed topic in the bank."""
    query = select(Topic).where(Topic.status != TopicStatus.CLOSED)
    if exclude_topic_id is not None:
        query = query.where(Topic.id != exclude_topic_id)
    topics = {topic.id: topic for topic in db.scalars(query)}
    corpus = [(t.id, topic_text(t.title, t.description, t.keywords)) for t in topics.values()]
    ranked = rank_similar(topic_text(title, description, keywords), corpus)
    return [
        SimilarTopic(
            topic_id=topic_id,
            title=topics[topic_id].title,
            status=topics[topic_id].status,
            professor_name=topics[topic_id].professor.full_name,
            score=score,
            is_duplicate=score >= BLOCKING_THRESHOLD,
        )
        for topic_id, score in ranked
    ]


def get_owned_topic(db: Session, topic_id: int, user: User) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El tema no existe.")
    if user.role != UserRole.ADMIN and topic.professor_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el profesor que publicó el tema puede modificarlo.")
    return topic


@router.get("", response_model=list[TopicOut])
def list_topics(
    q: str | None = Query(default=None, description="Texto libre: título, descripción o palabras clave"),
    topic_status: TopicStatus | None = Query(default=None, alias="status"),
    research_line: str | None = None,
    program: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Topic).order_by(Topic.created_at.desc())
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(Topic.title.ilike(pattern), Topic.description.ilike(pattern), Topic.keywords.ilike(pattern))
        )
    if topic_status:
        query = query.where(Topic.status == topic_status)
    if research_line:
        query = query.where(Topic.research_line == research_line)
    if program:
        query = query.where(Topic.program == program)
    return [topic_to_out(topic) for topic in db.scalars(query)]


@router.get("/filters")
def list_filters(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Distinct values used by the search filters in the UI."""
    lines = db.scalars(select(Topic.research_line).distinct().order_by(Topic.research_line)).all()
    programs = db.scalars(select(Topic.program).distinct().order_by(Topic.program)).all()
    return {"research_lines": lines, "programs": programs}


@router.get("/mine", response_model=list[TopicOut])
def list_my_topics(db: Session = Depends(get_db), user: User = Depends(professor_or_admin)):
    query = select(Topic).where(Topic.professor_id == user.id).order_by(Topic.created_at.desc())
    return [topic_to_out(topic) for topic in db.scalars(query)]


@router.post("/similarity", response_model=list[SimilarTopic])
def check_similarity(
    payload: SimilarityRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Lets anyone check whether an idea is already in the bank before proposing it."""
    return find_similar_topics(db, payload.title, payload.description, payload.keywords, payload.exclude_topic_id)


@router.get("/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El tema no existe.")
    return topic_to_out(topic)


@router.post("", response_model=TopicCreateResult, status_code=status.HTTP_201_CREATED)
def create_topic(payload: TopicCreate, db: Session = Depends(get_db), user: User = Depends(professor_or_admin)):
    similar = find_similar_topics(db, payload.title, payload.description, payload.keywords)
    duplicates = [item for item in similar if item.is_duplicate]
    if duplicates:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": "Ya existe un tema prácticamente igual en el banco. Ajusta el enfoque antes de publicarlo.",
                "similar_topics": [item.model_dump(mode="json") for item in duplicates],
            },
        )
    topic = Topic(**payload.model_dump(), professor_id=user.id)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return TopicCreateResult(topic=topic_to_out(topic), similar_topics=similar)


@router.put("/{topic_id}", response_model=TopicOut)
def update_topic(
    topic_id: int, payload: TopicUpdate, db: Session = Depends(get_db), user: User = Depends(professor_or_admin)
):
    topic = get_owned_topic(db, topic_id, user)
    if topic.accepted_count > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede editar un tema que ya tiene estudiantes aceptados.")
    changes = payload.model_dump(exclude_unset=True)
    if {"title", "description", "keywords"} & changes.keys():
        merged = {
            "title": changes.get("title", topic.title),
            "description": changes.get("description", topic.description),
            "keywords": changes.get("keywords", topic.keywords),
        }
        duplicates = [s for s in find_similar_topics(db, **merged, exclude_topic_id=topic.id) if s.is_duplicate]
        if duplicates:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "message": "Con esos cambios el tema quedaría duplicado con otro existente.",
                    "similar_topics": [item.model_dump(mode="json") for item in duplicates],
                },
            )
    for field, value in changes.items():
        setattr(topic, field, value)
    db.commit()
    db.refresh(topic)
    return topic_to_out(topic)


@router.post("/{topic_id}/close", response_model=TopicOut)
def close_topic(topic_id: int, db: Session = Depends(get_db), user: User = Depends(professor_or_admin)):
    """Withdraws a topic; pending applications are automatically rejected."""
    topic = get_owned_topic(db, topic_id, user)
    if topic.accepted_count > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede cerrar un tema con estudiantes aceptados.")
    topic.status = TopicStatus.CLOSED
    for application in topic.applications:
        if application.status == ApplicationStatus.PENDING:
            application.status = ApplicationStatus.REJECTED
            application.feedback = "El profesor retiró este tema del banco."
    db.commit()
    db.refresh(topic)
    return topic_to_out(topic)


@router.post("/{topic_id}/reopen", response_model=TopicOut)
def reopen_topic(topic_id: int, db: Session = Depends(get_db), user: User = Depends(professor_or_admin)):
    topic = get_owned_topic(db, topic_id, user)
    if topic.status != TopicStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se pueden reabrir temas cerrados.")
    duplicates = [
        s
        for s in find_similar_topics(db, topic.title, topic.description, topic.keywords, exclude_topic_id=topic.id)
        if s.is_duplicate
    ]
    if duplicates:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "Mientras estuvo cerrado se publicó un tema equivalente.", "similar_topics": [d.model_dump(mode="json") for d in duplicates]},
        )
    topic.status = TopicStatus.AVAILABLE
    db.commit()
    db.refresh(topic)
    return topic_to_out(topic)

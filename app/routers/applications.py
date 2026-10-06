"""Student applications to topics and professor review workflow."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import utc_now, Application, ApplicationStatus, Topic, TopicStatus, User, UserRole
from ..schemas import ApplicationCreate, ApplicationOut, ApplicationReview
from ..security import require_roles
from ..serializers import application_to_out

router = APIRouter(prefix="/api/applications", tags=["applications"])

student_only = require_roles(UserRole.STUDENT)
professor_or_admin = require_roles(UserRole.PROFESSOR, UserRole.ADMIN)

MAX_PENDING_APPLICATIONS = 3


def student_has_assigned_topic(db: Session, student_id: int) -> bool:
    return bool(
        db.scalar(
            select(func.count(Application.id)).where(
                Application.student_id == student_id, Application.status == ApplicationStatus.ACCEPTED
            )
        )
    )


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def apply_to_topic(payload: ApplicationCreate, db: Session = Depends(get_db), student: User = Depends(student_only)):
    topic = db.get(Topic, payload.topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El tema no existe.")
    if topic.status != TopicStatus.AVAILABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este tema ya no está disponible: fue tomado o cerrado.")
    if student_has_assigned_topic(db, student.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya tienes un tema de grado asignado.")

    pending_count = db.scalar(
        select(func.count(Application.id)).where(
            Application.student_id == student.id, Application.status == ApplicationStatus.PENDING
        )
    )
    if pending_count >= MAX_PENDING_APPLICATIONS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Solo puedes tener {MAX_PENDING_APPLICATIONS} postulaciones pendientes a la vez. Retira alguna para continuar.",
        )

    existing = db.scalar(
        select(Application).where(Application.topic_id == topic.id, Application.student_id == student.id)
    )
    if existing and existing.status != ApplicationStatus.WITHDRAWN:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya te postulaste a este tema.")

    if existing:  # re-applying after withdrawing
        application = existing
        application.status = ApplicationStatus.PENDING
        application.motivation = payload.motivation.strip()
        application.feedback = ""
        application.created_at = utc_now()
        application.reviewed_at = None
    else:
        application = Application(topic_id=topic.id, student_id=student.id, motivation=payload.motivation.strip())
        db.add(application)
    db.commit()
    db.refresh(application)
    return application_to_out(application)


@router.get("/mine", response_model=list[ApplicationOut])
def list_my_applications(db: Session = Depends(get_db), student: User = Depends(student_only)):
    query = (
        select(Application).where(Application.student_id == student.id).order_by(Application.created_at.desc())
    )
    return [application_to_out(a) for a in db.scalars(query)]


@router.post("/{application_id}/withdraw", response_model=ApplicationOut)
def withdraw_application(application_id: int, db: Session = Depends(get_db), student: User = Depends(student_only)):
    application = db.get(Application, application_id)
    if application is None or application.student_id != student.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La postulación no existe.")
    if application.status != ApplicationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se pueden retirar postulaciones pendientes.")
    application.status = ApplicationStatus.WITHDRAWN
    db.commit()
    db.refresh(application)
    return application_to_out(application)


@router.get("/received", response_model=list[ApplicationOut])
def list_received_applications(
    application_status: ApplicationStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(professor_or_admin),
):
    query = select(Application).join(Topic).order_by(Application.created_at.desc())
    if user.role != UserRole.ADMIN:
        query = query.where(Topic.professor_id == user.id)
    if application_status:
        query = query.where(Application.status == application_status)
    return [application_to_out(a) for a in db.scalars(query)]


@router.post("/{application_id}/review", response_model=ApplicationOut)
def review_application(
    application_id: int,
    payload: ApplicationReview,
    db: Session = Depends(get_db),
    user: User = Depends(professor_or_admin),
):
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La postulación no existe.")
    topic = application.topic
    if user.role != UserRole.ADMIN and topic.professor_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el profesor del tema puede revisar esta postulación.")
    if application.status != ApplicationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta postulación ya fue revisada.")
    if payload.decision not in (ApplicationStatus.ACCEPTED, ApplicationStatus.REJECTED):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La decisión debe ser 'accepted' o 'rejected'.")

    now = utc_now()
    application.feedback = payload.feedback.strip()
    application.reviewed_at = now

    if payload.decision == ApplicationStatus.REJECTED:
        application.status = ApplicationStatus.REJECTED
        db.commit()
        db.refresh(application)
        return application_to_out(application)

    # --- Acceptance: enforce "one topic per student" and "no over-assignment" ---
    if topic.status != TopicStatus.AVAILABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "El tema ya no tiene cupos disponibles.")
    if student_has_assigned_topic(db, application.student_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "El estudiante ya fue aceptado en otro tema.")

    application.status = ApplicationStatus.ACCEPTED

    # The student is now assigned: withdraw their other pending applications.
    other_pending = db.scalars(
        select(Application).where(
            Application.student_id == application.student_id,
            Application.status == ApplicationStatus.PENDING,
            Application.id != application.id,
        )
    )
    for other in other_pending:
        other.status = ApplicationStatus.WITHDRAWN
        other.feedback = "Retirada automáticamente: el estudiante fue aceptado en otro tema."
        other.reviewed_at = now

    db.flush()
    db.refresh(topic)
    if topic.accepted_count >= topic.max_students:
        topic.status = TopicStatus.ASSIGNED
        for other in topic.applications:
            if other.status == ApplicationStatus.PENDING:
                other.status = ApplicationStatus.REJECTED
                other.feedback = "Cupos completos: el tema ya fue asignado."
                other.reviewed_at = now

    db.commit()
    db.refresh(application)
    return application_to_out(application)

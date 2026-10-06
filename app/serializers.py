"""Convert ORM objects into response schemas."""
from .models import Application, Topic
from .schemas import ApplicationOut, TopicOut


def topic_to_out(topic: Topic) -> TopicOut:
    return TopicOut(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        research_line=topic.research_line,
        program=topic.program,
        keywords=topic.keywords,
        max_students=topic.max_students,
        status=topic.status,
        professor_id=topic.professor_id,
        professor_name=topic.professor.full_name,
        accepted_count=topic.accepted_count,
        pending_count=topic.pending_count,
        created_at=topic.created_at,
    )


def application_to_out(application: Application) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        topic_id=application.topic_id,
        topic_title=application.topic.title,
        student_id=application.student_id,
        student_name=application.student.full_name,
        student_email=application.student.email,
        motivation=application.motivation,
        status=application.status,
        feedback=application.feedback,
        created_at=application.created_at,
        reviewed_at=application.reviewed_at,
    )

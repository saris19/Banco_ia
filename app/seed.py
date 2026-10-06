"""Demo data so the prototype can be shown right away.

All people below are fictional. Every demo account uses the password: demo1234
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import utc_now, Application, ApplicationStatus, Topic, TopicStatus, User, UserRole
from .security import hash_password

DEMO_PASSWORD = "demo1234"

DEMO_USERS = [
    ("Coordinación de Programa", "admin@demo.edu.co", UserRole.ADMIN),
    ("Laura Benavides Rosero", "laura.benavides@demo.edu.co", UserRole.PROFESSOR),
    ("Andrés Muñoz Guerrero", "andres.munoz@demo.edu.co", UserRole.PROFESSOR),
    ("Camila Ortiz Pantoja", "camila.ortiz@demo.edu.co", UserRole.STUDENT),
    ("Juan David Erazo", "juan.erazo@demo.edu.co", UserRole.STUDENT),
    ("Valentina Chamorro", "valentina.chamorro@demo.edu.co", UserRole.STUDENT),
]

DEMO_TOPICS = [
    {
        "professor": "laura.benavides@demo.edu.co",
        "title": "Detección temprana de deserción estudiantil con aprendizaje automático",
        "description": "Construir un modelo predictivo que identifique estudiantes en riesgo de abandonar el "
        "programa a partir de notas, asistencia y uso de plataformas virtuales, con un tablero para bienestar universitario.",
        "research_line": "Inteligencia artificial",
        "keywords": "machine learning, deserción, analítica académica",
        "max_students": 2,
    },
    {
        "professor": "laura.benavides@demo.edu.co",
        "title": "Chatbot de orientación para trámites académicos de la facultad",
        "description": "Asistente conversacional que responda preguntas frecuentes sobre matrícula, homologaciones y "
        "opciones de grado, conectado a la normativa institucional y con escalamiento a un funcionario.",
        "research_line": "Inteligencia artificial",
        "keywords": "chatbot, procesamiento de lenguaje natural, atención estudiantil",
        "max_students": 1,
    },
    {
        "professor": "andres.munoz@demo.edu.co",
        "title": "Monitoreo de calidad del aire en Pasto con sensores IoT de bajo costo",
        "description": "Diseñar una red de sensores de material particulado y una plataforma web que muestre en tiempo "
        "real la calidad del aire en distintos sectores de la ciudad, con alertas a la comunidad.",
        "research_line": "Internet de las cosas",
        "keywords": "IoT, sensores, calidad del aire, tiempo real",
        "max_students": 2,
    },
    {
        "professor": "andres.munoz@demo.edu.co",
        "title": "Evaluación de seguridad de aplicaciones web institucionales con OWASP",
        "description": "Aplicar la metodología OWASP Testing Guide sobre aplicaciones web de la universidad en un entorno "
        "controlado, documentar hallazgos y proponer un plan de remediación priorizado.",
        "research_line": "Ciberseguridad",
        "keywords": "OWASP, pruebas de penetración, seguridad web",
        "max_students": 1,
    },
    {
        "professor": "andres.munoz@demo.edu.co",
        "title": "Aplicación móvil de trazabilidad para pequeños productores de café de Nariño",
        "description": "Desarrollar una app que registre el proceso del café desde la finca hasta la venta, generando un "
        "código QR que el comprador final pueda consultar para conocer el origen del producto.",
        "research_line": "Desarrollo de software",
        "keywords": "trazabilidad, café, aplicación móvil, QR",
        "max_students": 2,
    },
]


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(User).limit(1)):
        return  # database already initialised

    password_hash = hash_password(DEMO_PASSWORD)
    users = {}
    for full_name, email, role in DEMO_USERS:
        user = User(full_name=full_name, email=email, password_hash=password_hash, role=role)
        db.add(user)
        users[email] = user
    db.flush()

    topics = []
    for index, data in enumerate(DEMO_TOPICS):
        data = dict(data)
        professor = users[data.pop("professor")]
        topic = Topic(
            **data,
            program="Ingeniería de Software",
            professor_id=professor.id,
            created_at=utc_now() - timedelta(days=20 - index * 3),
        )
        db.add(topic)
        topics.append(topic)
    db.flush()

    # Topic "OWASP" already taken by Juan David -> shows the "assigned" state.
    security_topic = topics[3]
    db.add(
        Application(
            topic_id=security_topic.id,
            student_id=users["juan.erazo@demo.edu.co"].id,
            motivation="Trabajo en temas de redes y seguridad y quiero profundizar en pruebas de aplicaciones web.",
            status=ApplicationStatus.ACCEPTED,
            feedback="Bienvenido. Iniciamos con la revisión del alcance la próxima semana.",
            reviewed_at=utc_now() - timedelta(days=5),
        )
    )
    security_topic.status = TopicStatus.ASSIGNED

    # A pending application so the professor inbox isn't empty.
    db.add(
        Application(
            topic_id=topics[0].id,
            student_id=users["valentina.chamorro@demo.edu.co"].id,
            motivation="Me interesa la analítica de datos educativos y ya cursé la electiva de minería de datos.",
        )
    )
    db.commit()

"""End-to-end API tests for the main business rules.

Run with:  pytest -q
"""
import os
import tempfile

import pytest

_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
# Set TEST_DATABASE_URL to run the suite against PostgreSQL (fresh, empty database).
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", f"sqlite:///{_db_file}")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASSWORD = "demo1234"


@pytest.fixture(scope="module")
def server():
    with TestClient(app) as client:  # runs lifespan -> creates tables + demo data
        yield client


def login(email: str) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client


def test_login_rejects_wrong_password(server):
    response = TestClient(app).post(
        "/api/auth/login", json={"email": "camila.ortiz@demo.edu.co", "password": "bad"}
    )
    assert response.status_code == 401


def test_requires_authentication(server):
    assert TestClient(app).get("/api/topics").status_code == 401


def test_student_cannot_publish_topics(server):
    student = login("camila.ortiz@demo.edu.co")
    response = student.post(
        "/api/topics",
        json={
            "title": "Un tema cualquiera de prueba",
            "description": "Descripción suficientemente larga para pasar la validación.",
            "research_line": "Pruebas",
            "program": "Ingeniería de Software",
        },
    )
    assert response.status_code == 403


def test_duplicate_topic_is_blocked(server):
    professor = login("andres.munoz@demo.edu.co")
    response = professor.post(
        "/api/topics",
        json={
            "title": "Monitoreo de la calidad del aire en Pasto con sensores IoT",
            "description": "Red de sensores IoT de bajo costo para medir material particulado y calidad del aire "
            "en tiempo real en sectores de la ciudad de Pasto con alertas.",
            "research_line": "Internet de las cosas",
            "program": "Ingeniería de Software",
            "keywords": "IoT, sensores, calidad del aire",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["similar_topics"][0]["is_duplicate"] is True


def test_similarity_check_finds_taken_topic(server):
    student = login("camila.ortiz@demo.edu.co")
    response = student.post(
        "/api/topics/similarity",
        json={"title": "Pruebas de seguridad OWASP en aplicaciones web de la universidad", "description": ""},
    )
    assert response.status_code == 200
    matches = response.json()
    assert matches and matches[0]["status"] == "assigned"


def test_original_topic_is_published(server):
    professor = login("laura.benavides@demo.edu.co")
    response = professor.post(
        "/api/topics",
        json={
            "title": "Realidad virtual para la enseñanza de anatomía básica",
            "description": "Entorno de realidad virtual que permita a estudiantes de primeros semestres explorar "
            "modelos tridimensionales del cuerpo humano con guías interactivas.",
            "research_line": "Realidad virtual",
            "program": "Ingeniería de Software",
            "keywords": "realidad virtual, educación, 3D",
            "max_students": 1,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["topic"]["status"] == "available"


def test_full_application_flow(server):
    student = login("camila.ortiz@demo.edu.co")
    professor = login("laura.benavides@demo.edu.co")
    topics = {t["title"]: t for t in student.get("/api/topics").json()}
    vr_topic = topics["Realidad virtual para la enseñanza de anatomía básica"]
    chatbot = topics["Chatbot de orientación para trámites académicos de la facultad"]
    owasp = topics["Evaluación de seguridad de aplicaciones web institucionales con OWASP"]

    # cannot apply to an already-assigned topic
    taken = student.post("/api/applications", json={"topic_id": owasp["id"], "motivation": "x" * 30})
    assert taken.status_code == 409

    first = student.post("/api/applications", json={"topic_id": vr_topic["id"], "motivation": "Me apasiona la RV " * 3})
    second = student.post("/api/applications", json={"topic_id": chatbot["id"], "motivation": "Me interesa el NLP " * 3})
    assert first.status_code == 201 and second.status_code == 201

    # no double application to the same topic
    again = student.post("/api/applications", json={"topic_id": vr_topic["id"], "motivation": "otra vez " * 5})
    assert again.status_code == 409

    # another student competes for the same 1-seat topic
    rival = login("valentina.chamorro@demo.edu.co")
    rival_app = rival.post("/api/applications", json={"topic_id": vr_topic["id"], "motivation": "También quiero " * 3})
    assert rival_app.status_code == 201

    # professor accepts Camila
    accepted = professor.post(
        f"/api/applications/{first.json()['id']}/review", json={"decision": "accepted", "feedback": "Bienvenida"}
    )
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"

    # topic is now assigned, rival rejected, Camila's other application withdrawn
    assert student.get(f"/api/topics/{vr_topic['id']}").json()["status"] == "assigned"
    rival_status = {a["topic_id"]: a["status"] for a in rival.get("/api/applications/mine").json()}
    assert rival_status[vr_topic["id"]] == "rejected"
    mine = {a["topic_id"]: a["status"] for a in student.get("/api/applications/mine").json()}
    assert mine[chatbot["id"]] == "withdrawn"

    # an assigned student can't apply anywhere else
    blocked = student.post("/api/applications", json={"topic_id": topics[
        "Monitoreo de calidad del aire en Pasto con sensores IoT de bajo costo"]["id"], "motivation": "x" * 30})
    assert blocked.status_code == 409


def test_professor_cannot_review_other_professors_applications(server):
    other = login("andres.munoz@demo.edu.co")
    pending = login("laura.benavides@demo.edu.co").get("/api/applications/received?status=pending").json()
    assert pending
    response = other.post(f"/api/applications/{pending[0]['id']}/review", json={"decision": "accepted"})
    assert response.status_code == 403


def test_pending_limit(server):
    client = TestClient(app)
    client.post(
        "/api/auth/register",
        json={"full_name": "Estudiante Nuevo", "email": "nuevo@demo.edu.co", "password": "secret1"},
    )
    professor = login("andres.munoz@demo.edu.co")
    ids = []
    for i in range(4):
        created = professor.post(
            "/api/topics",
            json={
                "title": f"Tema experimental número {i} sobre {['blockchain', 'drones', 'compiladores', 'videojuegos'][i]}",
                "description": f"Descripción detallada del tema {['cadenas de bloques', 'vuelo autónomo', 'análisis léxico', 'motores gráficos'][i]} con suficiente longitud.",
                "research_line": "Pruebas",
                "program": "Ingeniería de Software",
            },
        )
        assert created.status_code == 201, created.text
        ids.append(created.json()["topic"]["id"])
    results = [
        client.post("/api/applications", json={"topic_id": tid, "motivation": "Quiero trabajar en esto " * 2}).status_code
        for tid in ids
    ]
    assert results == [201, 201, 201, 409]


def test_stats(server):
    stats = login("admin@demo.edu.co").get("/api/admin/stats").json()
    assert stats["topics"]["assigned"] >= 2
    assert stats["professors"] == 2

import os
from pathlib import Path
import pytest

test_url = os.environ.get("TEST_DATABASE_URL", "")
sqlite_test = test_url.startswith("sqlite:///") and test_url.endswith("quiz_test.sqlite3")
if not sqlite_test and (not test_url or not test_url.rstrip("/").endswith("quiz_test")):
    raise RuntimeError("Set TEST_DATABASE_URL to a dedicated PostgreSQL database named quiz_test. Tests erase its data.")
os.environ["DATABASE_URL"] = test_url
os.environ["COOKIE_SECURE"] = "false"
os.environ["APP_ORIGINS"] = "http://testserver,http://localhost:5173"

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.db import SessionLocal, engine
from app.main import app
from app.models import Account, Role
from app.security import hasher, limiter

TEST_PASSWORD = "test-only-admin-password"


@pytest.fixture(scope="session", autouse=True)
def migrate():
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    from app.initialize import initialize_database
    initialize_database()
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(migrate):
    with engine.begin() as db:
        if engine.dialect.name == "sqlite":
            from app.db import Base
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
        else:
            db.execute(text("TRUNCATE accounts, competitions RESTART IDENTITY CASCADE"))
    limiter.attempts.clear()
    with SessionLocal.begin() as db:
        db.add(Account(username="test-admin", name="Test Admin", email="test-admin@example.com", role=Role.ADMIN, password_hash=hasher.hash(TEST_PASSWORD)))


@pytest.fixture
def admin():
    with TestClient(app) as client:
        response = client.post("/api/v1/admin/login", json={"username": "test-admin", "password": TEST_PASSWORD})
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        yield client


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def build_edition(admin, count=2):
    c = admin.post("/api/v1/competitions", json={"title": "Cultură Generală", "description": "Test real"})
    assert c.status_code == 201, c.text
    e = admin.post(f"/api/v1/competitions/{c.json()['id']}/editions", json={"name": "Ediția 1", "password": "edition-password"})
    assert e.status_code == 201, e.text
    eid = e.json()["id"]
    questions = []
    for i in range(count):
        multiple = i % 2 == 1
        q = admin.post(f"/api/v1/editions/{eid}/questions", json={
            "text": f"Întrebarea {i + 1}", "type": "MULTIPLE_CHOICE" if multiple else "SINGLE_CHOICE",
            "options": [{"text": "Corect A", "is_correct": True}, {"text": "Varianta B", "is_correct": multiple}, {"text": "Greșit", "is_correct": False}],
        })
        assert q.status_code == 201, q.text
        questions.append(q.json())
    return eid, questions


def join_client(client, eid, name="Andrei"):
    r = client.post(f"/api/v1/editions/{eid}/join", json={"name": name, "password": "edition-password"})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    return r.json()

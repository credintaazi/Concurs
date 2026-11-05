from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import func, select, text
from fastapi import HTTPException
from app.db import engine, SessionLocal
from app.initialize import initialize_database
from app.models import Participant, ParticipantAnswer
from app.schemas import AnswerInput
from app.services import submit_answer
from conftest import build_edition

pytestmark = pytest.mark.skipif(engine.dialect.name != "sqlite", reason="SQLite-specific checks")


def test_sqlite_restart_preserves_data_and_enforces_foreign_keys(admin):
    eid, _ = build_edition(admin)
    initialize_database()
    engine.dispose()
    assert admin.get(f"/api/v1/editions/{eid}").status_code == 200
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert connection.scalar(text("PRAGMA journal_mode")) == "wal"


def test_sixty_simultaneous_answers_and_duplicate_rejection(admin):
    eid, questions = build_edition(admin, 1)
    admin.post(f"/api/v1/editions/{eid}/open")
    with SessionLocal.begin() as db:
        people = [Participant(edition_id=eid, name=f"User {i}", normalized_name=f"user {i}") for i in range(60)]
        db.add_all(people)
        db.flush()
        ids = [p.id for p in people]
    assert admin.post(f"/api/v1/editions/{eid}/start").status_code == 200
    q = questions[0]
    payload = AnswerInput(question_id=q["id"], option_ids=[q["options"][0]["id"]])
    def answer(identity):
        with SessionLocal.begin() as db:
            try:
                submit_answer(db, eid, db.get(Participant, identity), payload)
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=60) as pool:
        assert list(pool.map(answer, ids)) == [200] * 60
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(answer, [ids[0], ids[0]])) == [409, 409]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ParticipantAnswer)) == 60
    assert admin.post(f"/api/v1/editions/{eid}/finish").status_code == 200

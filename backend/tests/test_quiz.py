from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect
from app.db import SessionLocal
from app.main import app
from app.models import Edition, Participant, Question, Status
from app.services import results_data, transition
from conftest import build_edition, join_client


def test_crud_and_reordering(admin):
    eid, qs = build_edition(admin, 3)
    assert admin.get("/api/v1/competitions").json()[0]["title"] == "Cultură Generală"
    assert admin.get(f"/api/v1/editions/{eid}").json()["status"] == "DRAFT"
    ids = [q["id"] for q in reversed(qs)]
    assert admin.put(f"/api/v1/editions/{eid}/questions/order", json={"question_ids": ids}).status_code == 200
    assert [q["id"] for q in admin.get(f"/api/v1/editions/{eid}/questions").json()] == ids
    assert admin.delete(f"/api/v1/questions/{qs[1]['id']}").status_code == 204
    remaining = admin.get(f"/api/v1/editions/{eid}/questions").json()
    assert [q["position"] for q in remaining] == [0, 1]
    assert admin.patch(f"/api/v1/editions/{eid}", json={"name": "Actualizat", "password": None}).json()["name"] == "Actualizat"


@pytest.mark.parametrize("kind,correct,texts,valid", [
    ("SINGLE_CHOICE", [True, False], ["A", "B"], True),
    ("SINGLE_CHOICE", [True, True], ["A", "B"], False),
    ("SINGLE_CHOICE", [False, False], ["A", "B"], False),
    ("MULTIPLE_CHOICE", [True, True], ["A", "B"], True),
    ("MULTIPLE_CHOICE", [True, False], ["A", "B"], False),
    ("SINGLE_CHOICE", [True], ["A"], False),
    ("SINGLE_CHOICE", [True, False], ["A", "  "], False),
])
def test_question_validation(admin, kind, correct, texts, valid):
    eid, _ = build_edition(admin, 0)
    r = admin.post(f"/api/v1/editions/{eid}/questions", json={"text": "O întrebare", "type": kind,
        "options": [{"text": t, "is_correct": c} for t, c in zip(texts, correct)]})
    assert r.status_code == (201 if valid else 422)


def test_join_auth_and_name_uniqueness(admin, client):
    eid, _ = build_edition(admin)
    url = f"/api/v1/editions/{eid}"
    assert client.post(url + "/join", json={"name": "Andrei", "password": "edition-password"}).status_code == 409
    assert admin.post(url + "/open").status_code == 200
    assert client.post(url + "/join", json={"name": "Andrei", "password": "wrong"}).status_code == 401
    joined = join_client(client, eid)
    with TestClient(app) as duplicate:
        assert duplicate.post(url + "/join", json={"name": "  ANDREI  ", "password": "edition-password"}).status_code == 409
    assert client.get(url + "/state").json()["participant"]["id"] == joined["participant_id"]
    with SessionLocal() as db:
        assert db.scalar(select(Edition)).password_hash != "edition-password"
    assert "HttpOnly" in client.cookies.jar._cookies["testserver.local"]["/"][f"quiz_participant_{eid}"]._rest


def test_full_competition_and_scoring(admin, client):
    eid, qs = build_edition(admin, 5)
    url = f"/api/v1/editions/{eid}"
    assert admin.post(url + "/start").status_code == 409
    assert admin.post(url + "/open").status_code == 200
    join_client(client, eid)
    with TestClient(app) as second, TestClient(app) as third, TestClient(app) as late:
        join_client(second, eid, "Maria")
        join_client(third, eid, "Bogdan")
        waiting = client.get(url + "/state").json()
        assert waiting["question"] is None and waiting["participant_count"] == 3
        assert client.get(url + "/results").status_code == 409
        assert admin.post(url + "/start").json()["status"] == "LIVE"
        assert admin.post(url + "/start").json()["current_index"] == 0
        assert late.post(url + "/join", json={"name": "Late", "password": "edition-password"}).status_code == 409
        assert admin.post(url + "/finish").status_code == 409
        assert admin.delete(f"/api/v1/questions/{qs[0]['id']}").status_code == 409
        assert admin.post(url + "/questions", json={"text": "hack", "type": "SINGLE_CHOICE", "options": [{"text": "A", "is_correct": True}, {"text": "B"}]}).status_code == 409
        for index, q in enumerate(qs):
            s = client.get(url + "/state").json()
            assert s["question"]["id"] == q["id"]
            assert "is_correct" not in str(s) and "points" not in str(s)
            assert len(str(s)) < 4000
            correct = [o["id"] for o in q["options"] if o["is_correct"]]
            response = client.post(url + "/answers", json={"question_id": q["id"], "option_ids": correct})
            assert response.status_code == 200, response.text
            assert client.post(url + "/answers", json={"question_id": q["id"], "option_ids": correct}).status_code == 409
            assert client.get(url + "/state").json()["answered"] is True
            # Partial multiple-choice selections get zero, exact matches get one.
            assert second.post(url + "/answers", json={"question_id": q["id"], "option_ids": correct[:1]}).status_code == 200
            assert third.post(url + "/answers", json={"question_id": q["id"], "option_ids": correct[:1]}).status_code == 200
            assert admin.get(url + "/admin-state").json()["answer_count"] == 3
            if index < len(qs) - 1:
                assert admin.post(url + "/next", json={"expected_question_id": q["id"]}).status_code == 200
                assert admin.post(url + "/next", json={"expected_question_id": q["id"]}).status_code == 409
                assert client.post(url + "/answers", json={"question_id": q["id"], "option_ids": correct}).status_code == 409
        assert admin.post(url + "/finish").json()["status"] == "FINISHED"
        assert admin.post(url + "/finish").status_code == 200
        r = client.get(url + "/results").json()
        assert r["your_score"] == 5
        assert [p["score"] for p in r["leaderboard"]] == [5, 3, 3]
        assert [p["rank"] for p in r["leaderboard"]] == [1, 2, 2]
        assert all("is_correct" in o for q in r["questions"] for o in q["options"])
        # New connection and SQLAlchemy pool reload preserve both session and state.
        with TestClient(app) as reconnected:
            reconnected.cookies.update(client.cookies)
            assert reconnected.get(url + "/state").json()["status"] == "FINISHED"
            assert reconnected.get(url + "/results").json()["your_score"] == 5


def test_authorization_csrf_and_cross_edition(admin, client):
    eid, qs = build_edition(admin)
    url = f"/api/v1/editions/{eid}"
    assert client.get("/api/v1/competitions").status_code == 401
    assert client.get(url + "/questions").status_code == 401
    assert client.get(url + "/results").status_code == 401
    assert client.get(url + "/state").status_code == 401
    assert admin.post(url + "/open").status_code == 200
    join_client(client, eid)
    assert client.post(url + "/start").status_code == 401
    old = client.headers.pop("X-CSRF-Token")
    assert client.post(url + "/answers", json={"question_id": qs[0]["id"], "option_ids": [1]}).status_code == 403
    client.headers["X-CSRF-Token"] = old
    assert client.post(url + "/join", headers={"Origin": "https://evil.example"}, json={"name": "Xxx", "password": "a"}).status_code == 403
    other, _ = build_edition(admin)
    assert client.get(f"/api/v1/editions/{other}/state").status_code == 401
    token = admin.headers.pop("X-CSRF-Token")
    assert admin.post(url + "/start").status_code == 403
    admin.headers["X-CSRF-Token"] = token


def test_invalid_option_ids_and_foreign_questions(admin, client):
    eid, qs = build_edition(admin)
    url = f"/api/v1/editions/{eid}"
    admin.post(url + "/open")
    join_client(client, eid)
    admin.post(url + "/start")
    for ids in [[999999], [qs[1]["options"][0]["id"]], [qs[0]["options"][0]["id"]] * 2,
                [qs[0]["options"][0]["id"], qs[0]["options"][1]["id"]]]:
        assert client.post(url + "/answers", json={"question_id": qs[0]["id"], "option_ids": ids}).status_code == 422


def test_websocket_auth_room_isolation_and_reconnect(admin, client):
    eid, qs = build_edition(admin)
    other, _ = build_edition(admin)
    url = f"/api/v1/editions/{eid}"
    admin.post(url + "/open")
    join_client(client, eid)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/editions/{other}", headers={"origin": "http://testserver"}):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/editions/{eid}", headers={"origin": "https://evil.example"}):
            pass
    with client.websocket_connect(f"/ws/editions/{eid}", headers={"origin": "http://testserver"}) as socket:
        assert socket.receive_json()["event"] == "SYNC"
        admin.post(url + "/start")
        event = socket.receive_json()
        assert event["event"] == "QUIZ_STARTED" and event["edition_id"] == eid
        assert "question" not in event
        socket.send_text("ping")
        assert socket.receive_json()["event"] == "PONG"
    with client.websocket_connect(f"/ws/editions/{eid}", headers={"origin": "http://testserver"}) as socket:
        assert socket.receive_json()["event"] == "SYNC"
        assert client.get(url + "/state").json()["question"]["id"] == qs[0]["id"]


def test_concurrent_next_is_atomic(admin):
    eid, qs = build_edition(admin, 3)
    admin.post(f"/api/v1/editions/{eid}/open")
    admin.post(f"/api/v1/editions/{eid}/start")
    def advance():
        with SessionLocal() as db:
            try:
                transition(db, eid, "next", qs[0]["id"])
                db.commit()
                return 200
            except Exception as error:
                return getattr(error, "status_code", 500)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: advance(), range(2))) == [200, 409]
    with SessionLocal() as db:
        assert db.get(Edition, eid).current_index == 1


def test_join_start_race_serializes_on_edition(admin):
    eid, _ = build_edition(admin)
    admin.post(f"/api/v1/editions/{eid}/open")
    def enter():
        with TestClient(app) as p:
            return p.post(f"/api/v1/editions/{eid}/join", json={"name": "Concurrent", "password": "edition-password"}).status_code
    def begin():
        with SessionLocal.begin() as db:
            transition(db, eid, "start")
        return 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        join = pool.submit(enter)
        start = pool.submit(begin)
        assert join.result() in {200, 409}
        assert start.result() == 200
    with SessionLocal() as db:
        assert db.get(Edition, eid).status == Status.LIVE


def test_login_rate_limit_and_validation_redacts_password(client):
    for _ in range(15):
        assert client.post("/api/v1/admin/login", json={"username": "missing", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/admin/login", json={"username": "missing", "password": "wrong"}).status_code == 429
    secret = "private" * 40
    r = client.post("/api/v1/admin/login", json={"username": "missing", "password": secret})
    assert r.status_code == 422 and secret not in r.text


def test_results_refresh_participant_loaded_before_finish(admin, client):
    eid, qs = build_edition(admin, 1)
    url = f"/api/v1/editions/{eid}"
    admin.post(url + "/open")
    joined = join_client(client, eid)
    admin.post(url + "/start")
    assert client.post(url + "/answers", json={"question_id": qs[0]["id"], "option_ids": [qs[0]["options"][0]["id"]]}).status_code == 200
    with SessionLocal() as db:
        participant = db.get(Participant, joined["participant_id"])
        assert participant.final_score is None
        db.commit()  # Release the snapshot before another transaction finishes the edition.
        assert admin.post(url + "/finish").status_code == 200
        result = results_data(db, eid, participant)
        assert result["your_score"] == result["leaderboard"][0]["score"] == 1

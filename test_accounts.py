from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.db import SessionLocal
from app.main import app
from app.models import Account, AuthSession, Participant, Role, utcnow
from app.security import hasher
from app.services import submit_answer
from app.schemas import AnswerInput
from conftest import build_edition, join_client


def register(client, email="user@example.com", name="Participant"):
    response = client.post("/api/v1/auth/register", json={"email": email, "name": name, "password": "test-user-password"})
    assert response.status_code == 201, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return response.json()


def test_register_login_logout_and_persistent_session(client):
    result = register(client, "Mixed.Case@Example.com")
    assert result["user"]["role"] == "USER"
    assert result["user"]["email"] == "mixed.case@example.com"
    assert "password" not in str(result)
    with SessionLocal() as db:
        user = db.get(Account, result["user"]["id"])
        assert user.password_hash != "test-user-password"
        assert hasher.verify(user.password_hash, "test-user-password")
        assert db.scalar(select(AuthSession)).token_hash != client.cookies.get("quiz_account")
    with TestClient(app) as refreshed:
        refreshed.cookies.update(client.cookies)
        assert refreshed.get("/api/v1/auth/session").json()["user"] == result["user"]
        assert refreshed.post("/api/v1/auth/logout").status_code == 403
        refreshed.headers["X-CSRF-Token"] = result["csrf"]
        cookie = refreshed.cookies.get("quiz_account")
        assert refreshed.post("/api/v1/auth/logout").status_code == 200
        refreshed.cookies.set("quiz_account", cookie)
        assert refreshed.get("/api/v1/auth/session").json()["user"] is None
    assert client.post("/api/v1/auth/login", json={"email": "mixed.case@example.com", "password": "incorrect"}).status_code == 401
    login = client.post("/api/v1/auth/login", json={"email": "MIXED.CASE@example.com", "password": "test-user-password"})
    assert login.status_code == 200 and login.json()["user"]["role"] == "USER"
    assert client.post("/api/v1/auth/register", json={"email": "mixed.case@example.com", "name": "Duplicate", "password": "test-user-password"}).status_code == 409


@pytest.mark.parametrize("change", [{"role": "ADMIN"}, {"username": "admin"}, {"email": "invalid"}, {"password": "short"}, {"name": " "}])
def test_public_registration_cannot_set_role_and_validates_input(client, change):
    body = {"email": "new@example.com", "name": "Test User", "password": "test-user-password", **change}
    assert client.post("/api/v1/auth/register", json=body).status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(Account).where(Account.email == "new@example.com")) is None


def test_user_is_forbidden_from_every_admin_operation(admin, client):
    eid, qs = build_edition(admin)
    register(client)
    cid = admin.get(f"/api/v1/editions/{eid}").json()["competition_id"]
    operations = [
        ("GET", "/admin/session", None), ("GET", "/admin/overview", None),
        ("GET", "/competitions", None), ("POST", "/competitions", {"title": "Attack"}),
        ("GET", f"/competitions/{cid}", None), ("PATCH", f"/competitions/{cid}", {"title": "Attack"}),
        ("DELETE", f"/competitions/{cid}", None), ("GET", f"/competitions/{cid}/editions", None),
        ("POST", f"/competitions/{cid}/editions", {"name": "Attack", "password": "longpassword"}),
        ("GET", f"/editions/{eid}", None), ("GET", f"/editions/{eid}/admin-state", None),
        ("PATCH", f"/editions/{eid}", {"name": "Attack"}), ("DELETE", f"/editions/{eid}", None),
        ("GET", f"/editions/{eid}/questions", None), ("DELETE", f"/questions/{qs[0]['id']}", None),
        ("PUT", f"/editions/{eid}/questions/order", {"question_ids": [q["id"] for q in qs]}),
        ("GET", f"/editions/{eid}/participants", None), ("GET", f"/editions/{eid}/live-results", None),
    ]
    operations += [("POST", f"/editions/{eid}/{command}", {"expected_revision": 0, "expected_question_id": qs[0]["id"], "scheduled_at": (utcnow() + timedelta(days=1)).isoformat()})
                   for command in ["open", "start", "next", "finish", "pause", "resume", "stop", "schedule"]]
    for method, path, body in operations:
        response = client.request(method, "/api/v1" + path, **({"json": body} if body is not None else {}))
        assert response.status_code == 403, (method, path, response.status_code, response.text)
    assert client.get(f"/api/v1/editions/{eid}/results").status_code == 409


def test_email_admin_login_and_server_side_role_recheck(admin, client):
    from conftest import TEST_PASSWORD
    login = client.post("/api/v1/auth/login", json={"email": "test-admin@example.com", "password": TEST_PASSWORD})
    assert login.status_code == 200 and login.json()["user"]["role"] == "ADMIN"
    assert client.get("/api/v1/competitions").status_code == 200
    with SessionLocal.begin() as db:
        db.scalar(select(Account).where(Account.email == "test-admin@example.com")).role = Role.USER
    assert client.get("/api/v1/competitions").status_code == 403
    assert client.get("/api/v1/auth/session").json()["user"]["role"] == "USER"


def test_account_participation_recovery_requires_same_account(admin, client):
    eid, qs = build_edition(admin)
    url = f"/api/v1/editions/{eid}"
    account = register(client)
    admin.post(url + "/open")
    join_client(client, eid)
    admin.post(url + "/start")
    assert client.post(url + "/answers", json={"question_id": qs[0]["id"], "option_ids": [qs[0]["options"][0]["id"]]}).status_code == 200
    client.cookies.delete(f"quiz_participant_{eid}")
    recovered = client.get(url + "/state")
    assert recovered.status_code == 200 and recovered.json()["answered"]
    assert client.get("/api/v1/auth/participations").json()[0]["id"] == eid
    client.headers["X-CSRF-Token"] = account["csrf"]
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get(url + "/state").status_code == 401
    register(client, "other@example.com", "Other")
    assert client.get(url + "/state").status_code == 403
    assert client.post(url + "/join", json={"name": "Other", "password": "edition-password"}).status_code == 409


def test_scheduling_pause_resume_stop_and_live_score(admin, client):
    eid, qs = build_edition(admin, 2)
    url = f"/api/v1/editions/{eid}"
    assert admin.post(url + "/schedule", json={"scheduled_at": (utcnow() - timedelta(days=1)).isoformat()}).status_code == 422
    assert admin.post(url + "/schedule", json={"scheduled_at": "2029-01-01T10:00:00"}).status_code == 422
    scheduled = admin.post(url + "/schedule", json={"scheduled_at": (utcnow() + timedelta(days=1)).isoformat()})
    assert scheduled.status_code == 200 and scheduled.json()["status"] == "SCHEDULED"
    assert client.get("/api/v1/public/editions").json()[0]["status"] == "SCHEDULED"
    assert admin.get("/api/v1/competitions").json()[0]["status"] == "SCHEDULED"
    assert admin.post(url + "/start").status_code == 409
    admin.post(url + "/open")
    join_client(client, eid)
    started = admin.post(url + "/start").json()
    with client.websocket_connect(f"/ws/editions/{eid}", headers={"origin": "http://testserver"}) as socket:
        socket.receive_json()
        paused = admin.post(url + "/pause", json={"expected_revision": started["revision"]}).json()
        assert paused["status"] == "PAUSED"
        assert socket.receive_json()["event"] == "QUIZ_PAUSED"
        s = client.get(url + "/state").json()
        assert s["status"] == "PAUSED" and s["question"]["id"] == qs[0]["id"]
        assert "is_correct" not in str(s)
        assert client.post(url + "/answers", json={"question_id": qs[0]["id"], "option_ids": [qs[0]["options"][0]["id"]]}).status_code == 409
        assert admin.post(url + "/next", json={"expected_question_id": qs[0]["id"]}).status_code == 409
        assert admin.delete(url).status_code == 409
        resumed = admin.post(url + "/resume", json={"expected_revision": paused["revision"]}).json()
        assert resumed["status"] == "LIVE" and resumed["current_index"] == 0
        assert socket.receive_json()["event"] == "QUIZ_RESUMED"
        assert admin.post(url + "/pause", json={"expected_revision": started["revision"]}).status_code == 409
    assert client.post(url + "/answers", json={"question_id": qs[0]["id"], "option_ids": [qs[0]["options"][0]["id"]]}).status_code == 200
    assert admin.get(url + "/live-results").json()["leaderboard"][0]["score"] == 1
    assert client.get(url + "/results").status_code == 409
    current = admin.get(url + "/admin-state").json()
    stopped = admin.post(url + "/stop", json={"expected_revision": current["revision"]})
    assert stopped.status_code == 200 and stopped.json()["results_published"]
    assert client.get(url + "/results").json()["your_score"] == 1


def test_participant_management_and_exclusion_preserves_answers(admin, client):
    eid, qs = build_edition(admin)
    url = f"/api/v1/editions/{eid}"
    admin.post(url + "/open")
    join_client(client, eid)
    pid = client.get(url + "/state").json()["participant"]["id"]
    assert admin.patch(url + f"/participants/{pid}", json={"name": "Renamed"}).status_code == 200
    assert client.get(url + "/state").json()["participant"]["name"] == "Renamed"
    admin.post(url + "/start")
    assert client.post(url + "/answers", json={"question_id": qs[0]["id"], "option_ids": [qs[0]["options"][0]["id"]]}).status_code == 200
    with SessionLocal() as db:
        stale = db.get(Participant, pid)
        assert stale.is_active
        db.commit()  # Allow the exclusion transaction to complete before checking stale state.
        assert admin.delete(url + f"/participants/{pid}").status_code == 204
        with pytest.raises(Exception) as error:
            submit_answer(db, eid, stale, AnswerInput(question_id=qs[0]["id"], option_ids=[qs[0]["options"][0]["id"]]))
        assert error.value.status_code == 409
    assert client.get(url + "/state").status_code == 401
    assert admin.get(url + "/live-results").json()["leaderboard"] == []
    assert admin.get(url + "/participants").json()[0]["is_active"] is False


def test_trusted_promotion_revokes_existing_sessions(client, monkeypatch):
    from app.manage import main
    register(client)
    monkeypatch.setattr("sys.argv", ["manage", "promote", "user@example.com"])
    main()
    assert client.get("/api/v1/auth/session").json()["user"] is None
    response = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "test-user-password"})
    assert response.json()["user"]["role"] == "ADMIN"
    assert client.get("/api/v1/competitions").status_code == 200


def test_catalog_auth_and_observer_cannot_read_questions_or_live_results(admin, client):
    eid, qs = build_edition(admin)
    register(client)
    admin.post(f"/api/v1/editions/{eid}/open")
    with client.websocket_connect("/ws/catalog", headers={"origin": "http://testserver"}) as socket:
        assert socket.receive_json()["event"] == "SYNC"
        admin.post(f"/api/v1/editions/{eid}/start")
        event = socket.receive_json()
        assert event["event"] == "QUIZ_STARTED" and event["edition_id"] == eid
        assert "question" not in event and "score" not in event
    assert client.get(f"/api/v1/editions/{eid}/state").status_code == 403
    assert client.get(f"/api/v1/editions/{eid}/questions").status_code == 403
    assert client.get(f"/api/v1/editions/{eid}/live-results").status_code == 403
    metadata = client.get(f"/api/v1/public/editions/{eid}").json()
    assert "is_correct" not in str(metadata) and "password" not in str(metadata)


def test_scoring_and_tied_ranks_ignore_speed_and_client_points(admin, client):
    eid, qs = build_edition(admin, 1)
    url = f"/api/v1/editions/{eid}"
    admin.post(url + "/open")
    join_client(client, eid, "First")
    with TestClient(app) as slower:
        join_client(slower, eid, "Second")
        admin.post(url + "/start")
        for participant, elapsed in [(client, 1), (slower, 999999)]:
            response = participant.post(url + "/answers", json={"question_id": qs[0]["id"], "option_ids": [qs[0]["options"][0]["id"]], "elapsed_ms": elapsed, "points": 999})
            assert response.status_code == 200
        assert admin.patch(url, json={"name": "Anunț actualizat în LIVE", "description": "Fără bonus de viteză"}).status_code == 200
        assert client.get(url + "/state").json()["name"] == "Anunț actualizat în LIVE"
        assert admin.patch(url, json={"name": "Test", "password": "new-password"}).status_code == 409
        admin.post(url + "/finish")
        leaderboard = client.get(url + "/results").json()["leaderboard"]
        assert [(p["score"], p["rank"]) for p in leaderboard] == [(1, 1), (1, 1)]

"""Restart the owned Windows development stack and verify a live edition survives.

Requires scripts/start-local.ps1 to be running. Creates/removes its own test data.
Session credentials remain in memory. Stop/start output goes to ignored .local/.
"""
from pathlib import Path
import subprocess
import secrets
import httpx
from dotenv import dotenv_values
from websockets.sync.client import connect

root = Path(__file__).resolve().parents[1]
configuration = dotenv_values(root / ".env")
base = "http://localhost:5173"
admin = httpx.Client(base_url=base + "/api/v1", timeout=20)
player = httpx.Client(base_url=base + "/api/v1", timeout=20)
competition_id = None


def request(client, method, path, body=None):
    response = client.request(method, path, **({"json": body} if body is not None else {}))
    response.raise_for_status()
    return response.json() if response.content else None


try:
    login = request(admin, "POST", "/admin/login", {"username": configuration["ADMIN_USERNAME"], "password": configuration["ADMIN_PASSWORD"]})
    admin.headers["X-CSRF-Token"] = login["csrf"]
    competition = request(admin, "POST", "/competitions", {"title": "Restart verification (temporary)"})
    competition_id = competition["id"]
    edition = request(admin, "POST", f"/competitions/{competition_id}/editions", {"name": "Restart persistence", "password": "temporary-test-password"})
    eid = edition["id"]
    url = f"/editions/{eid}"
    qs = [request(admin, "POST", url + "/questions", {"text": f"Persistent question {i}", "type": "SINGLE_CHOICE", "options": [{"text": "Yes", "is_correct": True}, {"text": "No", "is_correct": False}]}) for i in range(2)]
    account = request(player, "POST", "/auth/register", {"name": "Restart test account", "email": f"e2e-restart-{secrets.token_hex(6)}@example.com", "password": secrets.token_urlsafe(24)})
    request(admin, "POST", url + "/open")
    joined = request(player, "POST", url + "/join", {"name": "Persistence participant", "password": "temporary-test-password"})
    player.headers["X-CSRF-Token"] = joined["csrf"]
    request(admin, "POST", url + "/start")
    request(player, "POST", url + "/answers", {"question_id": qs[0]["id"], "option_ids": [qs[0]["options"][0]["id"]]})
    state = request(admin, "GET", url + "/admin-state")
    request(admin, "POST", url + "/pause", {"expected_revision": state["revision"]})
    before = request(player, "GET", url + "/state")
    assert before["status"] == "PAUSED" and before["answered"]
    with (root / ".local" / "restart-verification.log").open("w", encoding="utf-8") as log:
        for action in ["stop-local.ps1", "start-local.ps1"]:
            command = ["powershell.exe", "-NoProfile", "-File", str(root / "scripts" / action)]
            if action == "start-local.ps1":
                command.append("-SkipInstall")
            subprocess.run(command, cwd=root,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    after = request(player, "GET", url + "/state")
    assert after["status"] == "PAUSED"
    assert request(player, "GET", "/auth/session")["user"] == account["user"]
    assert after["revision"] == before["revision"]
    assert after["participant"] == before["participant"]
    assert after["question"] == before["question"] and after["answered"]
    assert after["selected_option_ids"] == before["selected_option_ids"]
    late = httpx.post(base + "/api/v1" + url + "/join", json={"name": "Late after restart", "password": "temporary-test-password"})
    assert late.status_code == 409
    cookie = "; ".join(f"{name}={value}" for name, value in player.cookies.items())
    with connect(f"ws://localhost:5173/ws/editions/{eid}", origin=base, additional_headers={"Cookie": cookie}, close_timeout=3) as socket:
        import json
        assert json.loads(socket.recv(timeout=5))["event"] == "SYNC"
    request(admin, "POST", url + "/resume", {"expected_revision": after["revision"]})
    request(admin, "POST", url + "/next", {"expected_question_id": qs[0]["id"]})
    assert request(player, "GET", url + "/state")["question"]["id"] == qs[1]["id"]
    request(admin, "POST", url + "/finish")
    assert request(player, "GET", url + "/results")["your_score"] == 1
    print("PASS: PostgreSQL, backend and frontend restarted; PAUSED state, ADMIN/USER sessions, linked participation, answer and registration cutoff preserved; WebSocket reauthenticated; resumed same question and persisted final score.")
finally:
    if competition_id:
        try:
            editions = request(admin, "GET", f"/competitions/{competition_id}/editions")
            for e in editions:
                if e["status"] in {"LIVE", "PAUSED"}:
                    state = request(admin, "GET", f"/editions/{e['id']}/admin-state")
                    request(admin, "POST", f"/editions/{e['id']}/stop", {"expected_revision": state["revision"]})
            request(admin, "DELETE", f"/competitions/{competition_id}")
        except Exception as error:
            print(f"Temporary test cleanup failed: {type(error).__name__}")
    admin.close()
    player.close()

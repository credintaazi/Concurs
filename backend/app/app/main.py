from contextlib import asynccontextmanager
import asyncio
from anyio import from_thread
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .db import SessionLocal, get_db
from .models import Account, AuthSession, Competition, Edition, Participant, Question, Role, Status
from .auth import account_data, rotate_session, router as auth_router
from .realtime import hub
from .schemas import (AnswerInput, CompetitionInput, EditionInput, EditionUpdate, Join, Login,
                      NextInput, ParticipantUpdate, QuestionInput, ReorderInput, RevisionInput, ScheduleInput)
from .security import (account_from_cookies, dummy_hash, hasher, issue_session, limiter,
                       participant_from_cookies, require_account, require_admin, require_participant, verify_password)
from .services import (competition_data, edition_data, get_or_404, lock_edition, normalize_name,
                       question_data, questions_for, require_editable, results_data, save_question,
                       live_leaderboard, state_data, submit_answer, transition)

@asynccontextmanager
async def lifespan(app):
    from .initialize import initialize_database
    from .bootstrap import bootstrap
    await run_in_threadpool(initialize_database)
    await run_in_threadpool(bootstrap)
    yield


app = FastAPI(lifespan=lifespan, title="Quiz Arena API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json",
              swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect")
API = "/api/v1"
app.include_router(auth_router)


def authorize_admin(request, db):
    return require_admin(require_account(request, db))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin not in settings.origins:
            return JSONResponse({"detail": "Origine nepermisă."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cererile cross-site nu sunt permise."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse({"detail": "Operația intră în conflict cu date existente. Reîncarcă și încearcă din nou."}, status_code=409)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Exclude raw input so passwords are never reflected in error payloads.
    errors = [{"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse({"detail": "Verifică datele introduse.", "errors": errors}, status_code=422)


@app.get(API + "/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post(API + "/admin/login")
def login(payload: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    limiter.check(request, "admin-login")
    admin = db.scalar(select(Account).where(Account.username == payload.username, Account.role == Role.ADMIN))
    valid = verify_password(admin.password_hash if admin else dummy_hash, payload.password)
    if not admin or not valid:
        raise HTTPException(401, "Nume de utilizator sau parolă incorectă.")
    auth = rotate_session(db, response, request, admin)
    db.commit()
    return {"username": admin.username, "user": account_data(admin), "csrf": auth.csrf}


@app.get(API + "/admin/session")
def admin_session(auth=Depends(require_admin), db: Session = Depends(get_db)):
    account = db.get(Account, auth.account_id)
    return {"username": account.username or account.name, "user": account_data(account), "csrf": auth.csrf}


@app.get(API + "/admin/overview", dependencies=[Depends(require_admin)])
def overview(db: Session = Depends(get_db)):
    return {"editions": db.scalar(select(func.count()).select_from(Edition)),
            "participants": db.scalar(select(func.count()).select_from(Participant)),
            "live": db.scalar(select(func.count()).select_from(Edition).where(Edition.status == Status.LIVE))}


@app.post(API + "/admin/logout")
def logout(response: Response, auth=Depends(require_admin), db: Session = Depends(get_db)):
    db.delete(auth)
    db.commit()
    response.delete_cookie("quiz_admin", path="/")
    response.delete_cookie("quiz_account", path="/")
    return {"ok": True}


@app.get(API + "/competitions", dependencies=[Depends(require_admin)])
def competitions(db: Session = Depends(get_db)):
    return [competition_data(c, db) for c in db.scalars(select(Competition).order_by(Competition.created_at.desc()))]


@app.post(API + "/competitions", status_code=201, dependencies=[Depends(require_admin)])
def create_competition(payload: CompetitionInput, db: Session = Depends(get_db)):
    c = Competition(**payload.model_dump())
    db.add(c)
    db.commit()
    return competition_data(c)


@app.get(API + "/competitions/{competition_id}", dependencies=[Depends(require_admin)])
def competition(competition_id: int, db: Session = Depends(get_db)):
    return competition_data(get_or_404(db, Competition, competition_id), db)


@app.patch(API + "/competitions/{competition_id}", dependencies=[Depends(require_admin)])
def update_competition(competition_id: int, payload: CompetitionInput, db: Session = Depends(get_db)):
    c = get_or_404(db, Competition, competition_id)
    c.title, c.description = payload.title, payload.description
    db.commit()
    return competition_data(c)


@app.delete(API + "/competitions/{competition_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_competition(competition_id: int, db: Session = Depends(get_db)):
    c = db.scalar(select(Competition).where(Competition.id == competition_id).with_for_update())
    if not c:
        raise HTTPException(404, "Concursul nu există.")
    editions = list(db.scalars(select(Edition).where(Edition.competition_id == competition_id).order_by(Edition.id).with_for_update()))
    if any(e.status in {Status.LIVE, Status.PAUSED} for e in editions):
        raise HTTPException(409, "Un concurs cu ediții LIVE nu poate fi șters.")
    db.delete(c)
    db.commit()


@app.get(API + "/competitions/{competition_id}/editions", dependencies=[Depends(require_admin)])
def editions(competition_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Competition, competition_id)
    return [edition_data(db, e) for e in db.scalars(select(Edition).where(Edition.competition_id == competition_id).order_by(Edition.created_at.desc()))]


@app.post(API + "/competitions/{competition_id}/editions", status_code=201, dependencies=[Depends(require_admin)])
def create_edition(competition_id: int, payload: EditionInput, db: Session = Depends(get_db)):
    if not db.scalar(select(Competition).where(Competition.id == competition_id).with_for_update()):
        raise HTTPException(404, "Concursul nu există.")
    e = Edition(competition_id=competition_id, name=payload.name, description=payload.description, password_hash=hasher.hash(payload.password))
    db.add(e)
    db.commit()
    return edition_data(db, e)


@app.get(API + "/editions/{edition_id}", dependencies=[Depends(require_admin)])
def edition(edition_id: int, db: Session = Depends(get_db)):
    return edition_data(db, get_or_404(db, Edition, edition_id))


@app.patch(API + "/editions/{edition_id}", dependencies=[Depends(require_admin)])
def update_edition(edition_id: int, payload: EditionUpdate, db: Session = Depends(get_db)):
    e = lock_edition(db, edition_id)
    if e.status == Status.FINISHED:
        raise HTTPException(409, "Ediția finalizată nu poate fi modificată.")
    if payload.password:
        require_editable(e)
    e.name, e.description = payload.name, payload.description
    if payload.password:
        e.password_hash = hasher.hash(payload.password)
    e.revision += 1
    db.commit()
    from_thread.run(hub.broadcast, e.id, "EDITION_UPDATED", e.revision)
    return edition_data(db, e)


@app.delete(API + "/editions/{edition_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_edition(edition_id: int, db: Session = Depends(get_db)):
    e = lock_edition(db, edition_id)
    if e.status in {Status.LIVE, Status.PAUSED}:
        raise HTTPException(409, "O ediție LIVE nu poate fi ștearsă.")
    db.delete(e)
    db.commit()


@app.get(API + "/editions/{edition_id}/questions", dependencies=[Depends(require_admin)])
def questions(edition_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Edition, edition_id)
    return [question_data(q, reveal=True) for q in questions_for(db, edition_id)]


@app.post(API + "/editions/{edition_id}/questions", status_code=201, dependencies=[Depends(require_admin)])
def create_question(edition_id: int, payload: QuestionInput, db: Session = Depends(get_db)):
    q = save_question(db, lock_edition(db, edition_id), payload)
    db.commit()
    return question_data(q, reveal=True)


@app.patch(API + "/questions/{question_id}", dependencies=[Depends(require_admin)])
def update_question(question_id: int, payload: QuestionInput, db: Session = Depends(get_db)):
    q = get_or_404(db, Question, question_id)
    save_question(db, lock_edition(db, q.edition_id), payload, q)
    db.commit()
    return question_data(q, reveal=True)


@app.delete(API + "/questions/{question_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_question(question_id: int, db: Session = Depends(get_db)):
    q = get_or_404(db, Question, question_id)
    e = lock_edition(db, q.edition_id)
    require_editable(e)
    db.delete(q)
    db.flush()
    remaining = questions_for(db, e.id)
    if db.bind.dialect.name == "sqlite" and remaining:
        offset = max(q.position for q in remaining) + len(remaining) + 1
        for question in remaining:
            question.position += offset
        db.flush()
    for index, question in enumerate(remaining):
        question.position = index
    e.revision += 1
    db.commit()


@app.put(API + "/editions/{edition_id}/questions/order", dependencies=[Depends(require_admin)])
def reorder(edition_id: int, payload: ReorderInput, db: Session = Depends(get_db)):
    e = lock_edition(db, edition_id)
    require_editable(e)
    qs = {q.id: q for q in questions_for(db, edition_id)}
    if set(payload.question_ids) != set(qs) or len(payload.question_ids) != len(qs):
        raise HTTPException(422, "Ordinea trebuie să conțină fiecare întrebare exact o dată.")
    if db.bind.dialect.name == "sqlite" and qs:
        offset = max(q.position for q in qs.values()) + len(qs) + 1
        for q in qs.values():
            q.position += offset
        db.flush()
    for index, identity in enumerate(payload.question_ids):
        qs[identity].position = index
    e.revision += 1
    db.commit()
    return {"ok": True}


def control(edition_id, command, db, expected=None, revision=None):
    e = transition(db, edition_id, command, expected, expected_revision=revision)
    db.commit()
    from_thread.run(hub.broadcast, e.id, {"open": "EDITION_OPENED", "start": "QUIZ_STARTED", "next": "QUESTION_CHANGED", "finish": "QUIZ_FINISHED", "stop": "QUIZ_FINISHED", "pause": "QUIZ_PAUSED", "resume": "QUIZ_RESUMED"}[command], e.revision)
    return edition_data(db, e)


@app.post(API + "/editions/{edition_id}/open", dependencies=[Depends(require_admin)])
def open_edition(edition_id: int, db: Session = Depends(get_db)):
    return control(edition_id, "open", db)


@app.post(API + "/editions/{edition_id}/start", dependencies=[Depends(require_admin)])
def start(edition_id: int, db: Session = Depends(get_db)):
    return control(edition_id, "start", db)


@app.post(API + "/editions/{edition_id}/next", dependencies=[Depends(require_admin)])
def next_question(edition_id: int, payload: NextInput, db: Session = Depends(get_db)):
    return control(edition_id, "next", db, payload.expected_question_id)


@app.post(API + "/editions/{edition_id}/finish", dependencies=[Depends(require_admin)])
def finish(edition_id: int, db: Session = Depends(get_db)):
    return control(edition_id, "finish", db)


@app.post(API + "/editions/{edition_id}/pause", dependencies=[Depends(require_admin)])
def pause(edition_id: int, payload: RevisionInput, db: Session = Depends(get_db)):
    return control(edition_id, "pause", db, revision=payload.expected_revision)


@app.post(API + "/editions/{edition_id}/resume", dependencies=[Depends(require_admin)])
def resume(edition_id: int, payload: RevisionInput, db: Session = Depends(get_db)):
    return control(edition_id, "resume", db, revision=payload.expected_revision)


@app.post(API + "/editions/{edition_id}/stop", dependencies=[Depends(require_admin)])
def stop(edition_id: int, payload: RevisionInput, db: Session = Depends(get_db)):
    return control(edition_id, "stop", db, revision=payload.expected_revision)


@app.post(API + "/editions/{edition_id}/schedule", dependencies=[Depends(require_admin)])
def schedule(edition_id: int, payload: ScheduleInput, db: Session = Depends(get_db)):
    e = lock_edition(db, edition_id)
    if e.status not in {Status.DRAFT, Status.SCHEDULED}:
        raise HTTPException(409, "Poți programa doar o ediție în pregătire.")
    if not questions_for(db, e.id):
        raise HTTPException(409, "Adaugă minimum o întrebare înainte de programare.")
    e.status, e.scheduled_at = Status.SCHEDULED, payload.scheduled_at
    e.revision += 1
    db.commit()
    from_thread.run(hub.broadcast, e.id, "EDITION_SCHEDULED", e.revision)
    return edition_data(db, e)


@app.get(API + "/editions/{edition_id}/live-results", dependencies=[Depends(require_admin)])
def live_results(edition_id: int, db: Session = Depends(get_db)):
    data = live_leaderboard(db, edition_id)
    db.rollback()
    return data


@app.get(API + "/editions/{edition_id}/participants", dependencies=[Depends(require_admin)])
def participants(edition_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Edition, edition_id)
    return [{"id": p.id, "name": p.name, "joined_at": p.joined_at, "is_active": p.is_active, "has_account": p.account_id is not None} for p in db.scalars(select(Participant).where(
        Participant.edition_id == edition_id).order_by(Participant.joined_at))]


@app.patch(API + "/editions/{edition_id}/participants/{participant_id}", dependencies=[Depends(require_admin)])
def rename_participant(edition_id: int, participant_id: int, payload: ParticipantUpdate, db: Session = Depends(get_db)):
    e = lock_edition(db, edition_id)
    if e.status == Status.FINISHED:
        raise HTTPException(409, "Participanții nu se pot modifica după finalizare.")
    p = get_or_404(db, Participant, participant_id)
    if p.edition_id != edition_id:
        raise HTTPException(404, "Participantul nu există în ediție.")
    normalized = normalize_name(payload.name)
    if not 2 <= len(normalized) <= 160:
        raise HTTPException(422, "Nume invalid.")
    p.name, p.normalized_name = " ".join(payload.name.split()), normalized
    e.revision += 1
    db.commit()
    from_thread.run(hub.broadcast, e.id, "PARTICIPANT_UPDATED", e.revision)
    return {"ok": True}


@app.delete(API + "/editions/{edition_id}/participants/{participant_id}", status_code=204, dependencies=[Depends(require_admin)])
def remove_participant(edition_id: int, participant_id: int, db: Session = Depends(get_db)):
    e = lock_edition(db, edition_id)
    if e.status == Status.FINISHED:
        raise HTTPException(409, "Rezultatele publicate nu pot fi modificate.")
    p = get_or_404(db, Participant, participant_id)
    if p.edition_id != edition_id:
        raise HTTPException(404, "Participantul nu există în ediție.")
    if e.status in {Status.LIVE, Status.PAUSED}:
        p.is_active = False
        db.execute(delete(AuthSession).where(AuthSession.participant_id == p.id))
    else:
        db.delete(p)
    e.revision += 1
    db.commit()
    from_thread.run(hub.broadcast, e.id, "PARTICIPANT_REMOVED", e.revision)


@app.get(API + "/public/editions")
def public_editions(db: Session = Depends(get_db)):
    return [public_edition_data(db, e, c) for e, c in db.execute(
        select(Edition, Competition).join(Competition).where(Edition.status != Status.DRAFT).order_by(Edition.created_at.desc()))]


def public_edition_data(db, e, competition=None):
    return {**edition_data(db, e), "competition_title": (competition or get_or_404(db, Competition, e.competition_id)).title}


@app.get(API + "/public/editions/{edition_id}")
def public_edition(edition_id: int, db: Session = Depends(get_db)):
    e = get_or_404(db, Edition, edition_id)
    return public_edition_data(db, e)


@app.get(API + "/auth/participations")
def my_participations(auth=Depends(require_account), db: Session = Depends(get_db)):
    return [{**public_edition_data(db, e), "participant_name": p.name, "is_active": p.is_active} for e, p in db.execute(
        select(Edition, Participant).join(Participant).where(Participant.account_id == auth[0].id).order_by(Participant.joined_at.desc()))]


@app.post(API + "/editions/{edition_id}/join")
def join(edition_id: int, payload: Join, request: Request, response: Response, db: Session = Depends(get_db)):
    # School/church networks often share one public IP across many participants.
    limiter.check(request, "join", limit=120)
    e = lock_edition(db, edition_id)
    existing = participant_from_cookies(db, request.cookies, edition_id)
    if existing:
        return {"participant_id": existing[0].id, "csrf": existing[1].csrf}
    account_auth = account_from_cookies(db, request.cookies)
    account_id = account_auth[0].id if account_auth else None
    if account_id:
        member = db.scalar(select(Participant).where(Participant.edition_id == edition_id, Participant.account_id == account_id))
        if member:
            if not member.is_active:
                raise HTTPException(403, "Participarea ta la această ediție a fost închisă de administrator.")
            auth = issue_session(db, response, participant_id=member.id, edition_id=edition_id)
            db.commit()
            return {"participant_id": member.id, "csrf": auth.csrf}
    if e.status in {Status.LIVE, Status.PAUSED, Status.FINISHED}:
        raise HTTPException(409, "Concursul a început deja. Nu mai sunt permise înscrieri.")
    if e.status != Status.WAITING:
        raise HTTPException(409, "Înscrierile nu sunt deschise.")
    if not verify_password(e.password_hash, payload.password):
        raise HTTPException(401, "Parola ediției este incorectă.")
    normalized = normalize_name(payload.name)
    if not 2 <= len(normalized) <= 160:
        raise HTTPException(422, "Numele normalizat trebuie să aibă între 2 și 160 de caractere.")
    if db.scalar(select(Participant.id).where(Participant.edition_id == edition_id, Participant.normalized_name == normalized)):
        raise HTTPException(409, "Acest nume este deja folosit în ediție.")
    p = Participant(edition_id=edition_id, name=" ".join(payload.name.split()), normalized_name=normalized, account_id=account_id)
    db.add(p)
    db.flush()
    auth = issue_session(db, response, participant_id=p.id, edition_id=edition_id)
    e.revision += 1
    db.commit()
    from_thread.run(hub.broadcast, e.id, "PARTICIPANT_JOINED", e.revision)
    return {"participant_id": p.id, "csrf": auth.csrf}


@app.get(API + "/editions/{edition_id}/state")
def state(edition_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    # Prefer the participant cookie: even an admin previewing as a participant gets a safe payload.
    member = participant_from_cookies(db, request.cookies, edition_id)
    restored = False
    if not member:
        account = account_from_cookies(db, request.cookies)
        p = db.scalar(select(Participant).where(Participant.account_id == account[0].id,
            Participant.edition_id == edition_id, Participant.is_active.is_(True))) if account else None
        if p:
            member = p, issue_session(db, response, participant_id=p.id, edition_id=edition_id)
            restored = True
    if member:
        p, auth = member
        data = {**state_data(db, edition_id, p), "csrf": auth.csrf}
        if restored:
            db.commit()
        else:
            db.rollback()  # Release the snapshot lock before serializing the HTTP response.
        return data
    authorize_admin(request, db)
    data = state_data(db, edition_id)
    db.rollback()
    return data


@app.get(API + "/editions/{edition_id}/admin-state", dependencies=[Depends(require_admin)])
def admin_state(edition_id: int, db: Session = Depends(get_db)):
    data = state_data(db, edition_id)
    db.rollback()
    return data


@app.post(API + "/editions/{edition_id}/answers")
def answer(edition_id: int, payload: AnswerInput, auth=Depends(require_participant), db: Session = Depends(get_db)):
    e = submit_answer(db, edition_id, auth[0], payload)
    db.commit()
    from_thread.run(hub.broadcast, e.id, "ANSWER_SUBMITTED", e.revision)
    return {"accepted": True}


@app.get(API + "/editions/{edition_id}/results")
def results(edition_id: int, request: Request, db: Session = Depends(get_db)):
    member = participant_from_cookies(db, request.cookies, edition_id)
    if member:
        p = member[0]
        data = results_data(db, edition_id, p)
        db.rollback()
        return data
    require_account(request, db)
    data = results_data(db, edition_id)
    db.rollback()
    return data


def socket_authorized(socket: WebSocket, edition_id: int):
    with SessionLocal() as db:
        account = account_from_cookies(db, socket.cookies)
        if edition_id == 0:
            return account is not None
        edition = db.get(Edition, edition_id)
        if not edition:
            return False
        if account and (account[0].role == Role.ADMIN or edition.status != Status.DRAFT):
            return True
        return participant_from_cookies(db, socket.cookies, edition_id) is not None


@app.websocket("/ws/editions/{edition_id}")
async def websocket(socket: WebSocket, edition_id: int):
    if socket.headers.get("origin") not in settings.origins or not await run_in_threadpool(socket_authorized, socket, edition_id):
        await socket.close(code=1008)
        return
    await hub.connect(edition_id, socket)
    try:
        while True:
            try:
                message = await asyncio.wait_for(socket.receive_text(), timeout=45)
            except asyncio.TimeoutError:
                await socket.close(code=1001)
                break
            if not await run_in_threadpool(socket_authorized, socket, edition_id):
                await socket.close(code=1008)
                break
            if message == "ping":
                await socket.send_json({"event": "PONG"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(edition_id, socket)


@app.websocket("/ws/catalog")
async def catalog_socket(socket: WebSocket):
    await websocket(socket, 0)

import hashlib
import secrets
import time
from threading import Lock
from collections import defaultdict, deque
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import Account, AuthSession, Participant, Role, utcnow

hasher = PasswordHasher()
# A constant-time password verification path is also used for unknown users.
dummy_hash = hasher.hash(secrets.token_urlsafe(32))


def verify_password(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def participant_cookie(edition_id: int):
    return f"quiz_participant_{edition_id}"


def issue_session(db: Session, response: Response, *, account_id=None, participant_id=None, edition_id=None):
    token = secrets.token_urlsafe(48)
    account = db.get(Account, account_id) if account_id else None
    lifespan = timedelta(hours=12) if account and account.role == Role.ADMIN else timedelta(days=settings.session_days)
    session = AuthSession(token_hash=digest(token), csrf=secrets.token_hex(32), account_id=account_id,
                          participant_id=participant_id, expires_at=utcnow() + lifespan)
    db.execute(delete(AuthSession).where(AuthSession.expires_at < utcnow()))
    db.add(session)
    db.flush()
    response.set_cookie("quiz_account" if account_id else participant_cookie(edition_id), token,
                        max_age=int(lifespan.total_seconds()), httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/")
    return session


def find_session(db: Session, token: str | None):
    if not token:
        return None
    return db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(token), AuthSession.expires_at > utcnow()))


def check_csrf(request: Request, session: AuthSession):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
            raise HTTPException(403, "Sesiune invalidă. Reîncarcă pagina și încearcă din nou.")


def account_from_cookies(db: Session, cookies):
    session = find_session(db, cookies.get("quiz_account") or cookies.get("quiz_admin"))
    account = db.get(Account, session.account_id) if session and session.account_id else None
    return (account, session) if account else None


def require_account(request: Request, db: Session = Depends(get_db)):
    result = account_from_cookies(db, request.cookies)
    if not result:
        raise HTTPException(401, "Autentifică-te pentru a continua.")
    check_csrf(request, result[1])
    return result


def require_admin(auth=Depends(require_account)):
    if auth[0].role != Role.ADMIN:
        raise HTTPException(403, "Acces interzis. Este necesar rolul ADMIN.")
    return auth[1]


def participant_from_cookies(db: Session, cookies, edition_id: int):
    session = find_session(db, cookies.get(participant_cookie(edition_id)))
    participant = db.get(Participant, session.participant_id) if session and session.participant_id else None
    if not participant or participant.edition_id != edition_id or not participant.is_active:
        return None
    if participant.account_id:
        account = account_from_cookies(db, cookies)
        if not account or account[0].id != participant.account_id:
            return None
    return participant, session


def require_participant(request: Request, edition_id: int, db: Session = Depends(get_db)):
    result = participant_from_cookies(db, request.cookies, edition_id)
    if not result:
        raise HTTPException(401, "Intră în ediție pentru a continua.")
    check_csrf(request, result[1])
    return result


class RateLimiter:
    def __init__(self):
        self.attempts = defaultdict(deque)
        self.lock = Lock()

    def check(self, request: Request, scope: str, limit: int = 15):
        with self.lock:
            self._check(request, scope, limit)

    def _check(self, request: Request, scope: str, limit: int):
        now = time.monotonic()
        # Single process by design. Bound memory and expire inactive sources.
        for key in list(self.attempts):
            if not self.attempts[key] or self.attempts[key][-1] < now - 60:
                del self.attempts[key]
        key = (request.client.host if request.client else "unknown", scope)
        if key not in self.attempts and len(self.attempts) >= 10000:
            raise HTTPException(429, "Prea multe încercări. Încearcă din nou peste un minut.", headers={"Retry-After": "60"})
        attempts = self.attempts[key]
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= limit:
            raise HTTPException(429, "Prea multe încercări. Încearcă din nou peste un minut.", headers={"Retry-After": "60"})
        attempts.append(now)


limiter = RateLimiter()

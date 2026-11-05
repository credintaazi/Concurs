"""Email accounts and session lifecycle. Public registration can only create USER."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import Account, Role
from .schemas import AccountLogin, Register
from .security import (account_from_cookies, dummy_hash, find_session, hasher, issue_session,
                       limiter, require_account, verify_password)

router = APIRouter(prefix="/api/v1/auth", tags=["Accounts"])


def account_data(account: Account):
    return {"id": account.id, "email": account.email, "name": account.name, "role": account.role}


def rotate_session(db: Session, response: Response, request: Request, account: Account):
    old_sessions = {s.id: s for key in ("quiz_account", "quiz_admin")
                    if (s := find_session(db, request.cookies.get(key)))}
    for old in old_sessions.values():
        db.delete(old)
    session = issue_session(db, response, account_id=account.id)
    response.delete_cookie("quiz_admin", path="/")
    return session


@router.post("/register", status_code=201)
def register(payload: Register, request: Request, response: Response, db: Session = Depends(get_db)):
    limiter.check(request, "register", limit=10)
    if db.scalar(select(Account.id).where(Account.email == payload.email)):
        raise HTTPException(409, "Există deja un cont cu această adresă de email.")
    account = Account(email=payload.email, name=payload.name, password_hash=hasher.hash(payload.password), role=Role.USER)
    db.add(account)
    db.flush()
    session = rotate_session(db, response, request, account)
    db.commit()
    return {"user": account_data(account), "csrf": session.csrf}


@router.post("/login")
def login(payload: AccountLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    limiter.check(request, "account-login")
    account = db.scalar(select(Account).where(Account.email == payload.email))
    valid = verify_password(account.password_hash if account else dummy_hash, payload.password)
    if not account or not valid:
        raise HTTPException(401, "Email sau parolă incorectă.")
    session = rotate_session(db, response, request, account)
    db.commit()
    return {"user": account_data(account), "csrf": session.csrf}


@router.get("/session")
def session(request: Request, db: Session = Depends(get_db)):
    auth = account_from_cookies(db, request.cookies)
    return {"user": account_data(auth[0]), "csrf": auth[1].csrf} if auth else {"user": None, "csrf": None}


@router.post("/logout")
def logout(response: Response, auth=Depends(require_account), db: Session = Depends(get_db)):
    db.delete(auth[1])
    db.commit()
    for key in ("quiz_account", "quiz_admin"):
        response.delete_cookie(key, path="/")
    return {"ok": True}

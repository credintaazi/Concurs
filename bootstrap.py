from sqlalchemy import select
from .config import settings
from .db import SessionLocal
from pydantic import TypeAdapter, EmailStr
from .models import Account, Role
from .security import hasher


def bootstrap():
    with SessionLocal.begin() as db:
        if not db.scalar(select(Account).where(Account.role == Role.ADMIN).limit(1)):
            if len(settings.admin_password) < 12:
                raise RuntimeError("Set ADMIN_PASSWORD to at least 12 characters before initial startup.")
            email = str(TypeAdapter(EmailStr).validate_python(settings.admin_email)).casefold()
            if db.scalar(select(Account.id).where(Account.email == email)):
                raise RuntimeError("ADMIN_EMAIL belongs to an existing USER. Use the trusted promotion command explicitly.")
            db.add(Account(username=settings.admin_username, email=email, name=settings.admin_username,
                           role=Role.ADMIN, password_hash=hasher.hash(settings.admin_password)))


if __name__ == "__main__":
    bootstrap()

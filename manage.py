"""Trusted operator CLI; no public HTTP endpoint can grant administrator rights."""
import argparse
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import delete, select
from .db import SessionLocal
from .models import Account, AuthSession, Role


def main():
    parser = argparse.ArgumentParser(description="Manage Quiz Arena account roles from the server terminal.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-admins")
    promote = sub.add_parser("promote", help="Promote an existing registered account to ADMIN; revoke its existing sessions.")
    promote.add_argument("email")
    change = sub.add_parser("set-email", help="Set a migrated administrator's real email.")
    change.add_argument("email")
    change.add_argument("new_email")
    args = parser.parse_args()
    with SessionLocal.begin() as db:
        if args.command == "list-admins":
            for account in db.scalars(select(Account).where(Account.role == Role.ADMIN).order_by(Account.id)):
                print(f"{account.id}: {account.email} ({account.name})")
            return
        email = str(TypeAdapter(EmailStr).validate_python(args.email)).casefold()
        account = db.scalar(select(Account).where(Account.email == email).with_for_update())
        if not account:
            raise SystemExit("Account not found. Register the account first.")
        if args.command == "promote":
            account.role = Role.ADMIN
        else:
            if account.role != Role.ADMIN:
                raise SystemExit("set-email is restricted to administrator accounts.")
            new_email = str(TypeAdapter(EmailStr).validate_python(args.new_email)).casefold()
            if db.scalar(select(Account.id).where(Account.email == new_email, Account.id != account.id)):
                raise SystemExit("Email already in use.")
            account.email = new_email
        db.execute(delete(AuthSession).where(AuthSession.account_id == account.id))
    print("Account updated. Previous sessions revoked; sign in again.")


if __name__ == "__main__":
    main()

"""Operator commands for accounts, run on the server:

    python -m app.auth.cli reset-link someone@example.com
    python -m app.auth.cli grant-admin someone@example.com
    python -m app.auth.cli create-admin someone@example.com "Display Name"

`reset-link` prints a password-reset link to hand over (the no-SMTP fallback
when there's no admin in the app to generate one). `grant-admin` makes a user
a platform admin, who can e.g. edit track settings. `create-admin` makes the
first platform admin on a fresh deployment (prompts for a password; an
existing account is just promoted, its password left alone).
"""

import argparse
import asyncio
import getpass
from datetime import timedelta

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.models  # noqa: F401 -- registers all models on Base.metadata
from app.athletes.models import Athlete
from app.auth.models import User
from app.auth.schemas import validate_password_strength
from app.auth.service import create_reset_token, reset_link
from app.core.security import hash_password
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal


async def _reset_link(email: str) -> int:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user with email {email}")
            return 1
        hours = get_settings().password_reset_admin_expire_hours
        token, expires_at = await create_reset_token(db, user, timedelta(hours=hours))
        await db.commit()
    print(reset_link(token))
    print(f"Single use, expires {expires_at:%Y-%m-%d %H:%M} UTC.")
    return 0


async def _grant_admin(email: str) -> int:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user with email {email}")
            return 1
        user.is_platform_admin = True
        await db.commit()
    print(f"{email} is now a platform admin.")
    return 0


async def create_admin(db: AsyncSession, email: str, password: str, display_name: str) -> tuple[User, bool]:
    """Create a platform admin (with the athlete profile every user has), or
    promote the existing account with that email. Returns (user, created).
    """
    user = await db.scalar(select(User).where(User.email == email))
    if user is not None:
        user.is_platform_admin = True
        await db.commit()
        return user, False
    user = User(email=email, hashed_password=hash_password(password), is_platform_admin=True)
    db.add(user)
    await db.flush()
    db.add(Athlete(user_id=user.id, display_name=display_name))
    await db.commit()
    return user, True


async def _create_admin(email: str, display_name: str, password: str | None) -> int:
    try:
        email = str(TypeAdapter(EmailStr).validate_python(email))
    except ValidationError:
        print(f"{email!r} is not a valid email address")
        return 1
    async with AsyncSessionLocal() as db:
        if await db.scalar(select(User.id).where(User.email == email)) is None:
            if password is None:
                password = getpass.getpass("Password: ")
                if getpass.getpass("Repeat password: ") != password:
                    print("Passwords do not match")
                    return 1
            try:
                validate_password_strength(password)
            except ValueError as exc:
                print(exc)
                return 1
        _, created = await create_admin(db, email, password or "", display_name)
    print(f"Created platform admin {email}." if created else f"{email} already exists; now a platform admin.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.auth.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    reset = commands.add_parser("reset-link", help="print a password-reset link for a user")
    reset.add_argument("email")
    admin = commands.add_parser("grant-admin", help="make a user a platform admin")
    admin.add_argument("email")
    create = commands.add_parser("create-admin", help="create a platform admin account")
    create.add_argument("email")
    create.add_argument("display_name", nargs="?", default="Admin")
    create.add_argument("--password", help="avoid: ends up in shell history; omit to be prompted")
    args = parser.parse_args()
    if args.command == "create-admin":
        return asyncio.run(_create_admin(args.email, args.display_name, args.password))
    if args.command == "grant-admin":
        return asyncio.run(_grant_admin(args.email))
    return asyncio.run(_reset_link(args.email))


if __name__ == "__main__":
    raise SystemExit(main())

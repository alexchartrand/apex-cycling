"""Operator commands for accounts, run on the server:

    python -m app.auth.cli reset-link someone@example.com

Prints a password-reset link to hand over (the no-SMTP fallback when there's
no admin in the app to generate one).
"""

import argparse
import asyncio
from datetime import timedelta

from sqlalchemy import select

import app.db.models  # noqa: F401 -- registers all models on Base.metadata
from app.auth.models import User
from app.auth.service import create_reset_token, reset_link
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.auth.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    reset = commands.add_parser("reset-link", help="print a password-reset link for a user")
    reset.add_argument("email")
    args = parser.parse_args()
    return asyncio.run(_reset_link(args.email))


if __name__ == "__main__":
    raise SystemExit(main())

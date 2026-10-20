"""Operator commands for clubs, run on the server:

    python -m app.clubs.cli link-sqorz <club-slug> <sqorz-account-id>
    python -m app.clubs.cli unlink-sqorz <club-slug> <sqorz-account-id>

Linking a club to a sqorz account (a facility) lets that club's admins edit
the account's tracks (length, hidden checkpoints…). The same is available to
platform admins over the API (`POST /api/clubs/{id}/sqorz-accounts`).
"""

import argparse
import asyncio

from sqlalchemy import select

import app.db.models  # noqa: F401 -- registers all models on Base.metadata
from app.clubs.models import Club, ClubSqorzAccount
from app.db.session import AsyncSessionLocal
from app.training.models import Track


async def _link(slug: str, account_id: str, *, unlink: bool) -> int:
    async with AsyncSessionLocal() as db:
        club = await db.scalar(select(Club).where(Club.slug == slug))
        if club is None:
            print(f"No club with slug {slug}")
            return 1
        link = await db.scalar(
            select(ClubSqorzAccount).where(
                ClubSqorzAccount.club_id == club.id, ClubSqorzAccount.sqorz_account_id == account_id
            )
        )
        if unlink:
            if link is not None:
                await db.delete(link)
            await db.commit()
            print(f"{club.name} is no longer linked to sqorz account {account_id}.")
            return 0
        names = list(await db.scalars(select(Track.name).where(Track.sqorz_account_id == account_id)))
        if not names:
            print(f"No track has been imported for sqorz account {account_id} yet")
            return 1
        if link is None:
            db.add(ClubSqorzAccount(club_id=club.id, sqorz_account_id=account_id))
            await db.commit()
    print(f"{club.name} admins can now edit the tracks of sqorz account {account_id}: {', '.join(names)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.clubs.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("link-sqorz", "unlink-sqorz"):
        command = commands.add_parser(name)
        command.add_argument("club_slug")
        command.add_argument("sqorz_account_id")
    args = parser.parse_args()
    return asyncio.run(_link(args.club_slug, args.sqorz_account_id, unlink=args.command == "unlink-sqorz"))


if __name__ == "__main__":
    raise SystemExit(main())

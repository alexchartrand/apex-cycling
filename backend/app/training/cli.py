"""Operator commands for training data, run on the server:

    python -m app.training.cli recompute-records [--athlete ATHLETE_ID]
    python -m app.training.cli apply-facilities

Rebuilds every athlete's (or just one athlete's) personal records from their laps. Records are
refreshed automatically after each sqorz sync, so this is for backfilling
after a deploy that introduced them (or a change to how they're computed).

`apply-facilities` applies `app/training/facilities.json` (one entry per sqorz
account: the venue's name, location and build) to every track of each account
— see `app.training.facility`. The backend Dockerfiles run it on every start,
before uvicorn, so there is no need to run it by hand; a bad file makes it exit
1, which stops the backend from starting.
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select

import app.db.models  # noqa: F401 -- registers all models on Base.metadata
from app.athletes.models import Athlete
from app.db.session import AsyncSessionLocal
from app.training.facility import InvalidFacilityFile, import_profiles, known_profiles
from app.training.records_service import recompute_personal_records


async def _recompute_records(athlete_id: uuid.UUID | None) -> int:
    async with AsyncSessionLocal() as db:
        query = select(Athlete.id)
        if athlete_id is not None:
            query = query.where(Athlete.id == athlete_id)
        athlete_ids = list(await db.scalars(query))
        for athlete_id in athlete_ids:
            await recompute_personal_records(db, athlete_id)
        await db.commit()
    print(f"Recomputed personal records for {len(athlete_ids)} athletes.")
    return 0


async def _apply_facilities() -> int:
    try:
        profiles = known_profiles()
    except InvalidFacilityFile as exc:
        print(f"facilities.json: {exc}")
        return 1
    async with AsyncSessionLocal() as db:
        covered = await import_profiles(db, profiles)
        await db.commit()
    for account_id, names in covered.items():
        if names:
            print(f"Facility {account_id}: {len(names)} tracks ({', '.join(names)})")
        else:
            print(f"Facility {account_id}: no track yet (it gets the profile when sqorz first syncs it)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.training.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    recompute = commands.add_parser("recompute-records", help="rebuild personal records")
    recompute.add_argument("--athlete", type=uuid.UUID, help="only this athlete (default: everyone)")
    commands.add_parser("apply-facilities", help="apply facilities.json to the tracks")
    args = parser.parse_args()
    if args.command == "apply-facilities":
        return asyncio.run(_apply_facilities())
    return asyncio.run(_recompute_records(args.athlete))


if __name__ == "__main__":
    raise SystemExit(main())

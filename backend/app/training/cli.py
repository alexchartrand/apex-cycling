"""Operator commands for training data, run on the server:

    python -m app.training.cli recompute-records [--athlete ATHLETE_ID]

Rebuilds every athlete's (or just one athlete's) personal records from their laps. Records are
refreshed automatically after each sqorz sync, so this is for backfilling
after a deploy that introduced them (or a change to how they're computed).
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select

import app.db.models  # noqa: F401 -- registers all models on Base.metadata
from app.athletes.models import Athlete
from app.db.session import AsyncSessionLocal
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.training.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    recompute = commands.add_parser("recompute-records", help="rebuild personal records")
    recompute.add_argument("--athlete", type=uuid.UUID, help="only this athlete (default: everyone)")
    args = parser.parse_args()
    return asyncio.run(_recompute_records(args.athlete))


if __name__ == "__main__":
    raise SystemExit(main())

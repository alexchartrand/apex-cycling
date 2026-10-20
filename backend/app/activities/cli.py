"""Operator commands for imported activities, run on the server:

    python -m app.activities.cli recompute-metrics [--athlete ATHLETE_ID]

Rebuilds the power curve, normalized power and TSS of every activity with
power (or just one athlete's) from the stored samples. Metrics are computed on
import and TSS follows FTP changes by itself, so this is for backfilling after
a change to how they are computed.
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select

import app.db.models  # noqa: F401 -- registers all models on Base.metadata
from app.activities.metrics_service import rebuild_power_metrics
from app.activities.models import Activity
from app.db.session import AsyncSessionLocal


async def _recompute_metrics(athlete_id: uuid.UUID | None) -> int:
    rebuilt = 0
    async with AsyncSessionLocal() as db:
        query = select(Activity).where(Activity.has_power.is_(True))
        if athlete_id is not None:
            query = query.where(Activity.athlete_id == athlete_id)
        for activity in list(await db.scalars(query)):
            rebuilt += await rebuild_power_metrics(db, activity)
        await db.commit()
    print(f"Recomputed power metrics for {rebuilt} activities.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.activities.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    recompute = commands.add_parser("recompute-metrics", help="rebuild power curves, normalized power and TSS")
    recompute.add_argument("--athlete", type=uuid.UUID, help="only this athlete (default: everyone)")
    args = parser.parse_args()
    return asyncio.run(_recompute_metrics(args.athlete))


if __name__ == "__main__":
    raise SystemExit(main())

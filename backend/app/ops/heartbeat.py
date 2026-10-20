"""Worker liveness: a file for the container healthcheck and a DB row for the
admin page."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ops.models import WorkerHeartbeat

logger = logging.getLogger("ops.heartbeat")

HEARTBEAT_FILE = Path("/tmp/worker-heartbeat")
INGESTION_WORKER = "ingestion"
# The admin page calls the worker stale after this long without a beat.
STALE_AFTER_SECONDS = 180


def touch_heartbeat_file(path: Path = HEARTBEAT_FILE) -> None:
    path.touch()


async def record_beat(
    db: AsyncSession,
    *,
    started_at: datetime,
    now: datetime | None = None,
    poll_started_at: datetime | None = None,
    poll_finished_at: datetime | None = None,
    connections: int | None = None,
    failures: int | None = None,
    error: str | None = None,
    poll: bool = False,
    name: str = INGESTION_WORKER,
) -> None:
    """Upsert the worker's row. Pass `poll=True` with the poll fields to
    record a finished poll; a plain beat only refreshes `last_seen_at`.
    """
    now = now or datetime.now(timezone.utc)
    row = await db.get(WorkerHeartbeat, name)
    if row is None:
        row = WorkerHeartbeat(name=name, started_at=started_at, last_seen_at=now)
        db.add(row)
    row.started_at = started_at
    row.last_seen_at = now
    if poll:
        row.last_poll_started_at = poll_started_at
        row.last_poll_finished_at = poll_finished_at
        row.last_poll_connections = connections
        row.last_poll_failures = failures
        row.last_error = error
    await db.commit()

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import app.db.models  # noqa: F401 -- registers all models on Base.metadata before mapper configuration
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal
from app.ingestion.jobs import poll_active_connections, poll_intervals_connections
from app.ops.heartbeat import record_beat, touch_heartbeat_file

logger = logging.getLogger("ingestion.runner")

STARTED_AT = datetime.now(timezone.utc)


async def beat(**poll_fields) -> None:
    """Refresh the container-healthcheck file and the DB heartbeat. A DB
    hiccup is logged, not fatal: the next beat retries.
    """
    touch_heartbeat_file()
    try:
        async with AsyncSessionLocal() as db:
            await record_beat(db, started_at=STARTED_AT, **poll_fields)
    except Exception:
        logger.exception("Could not record the worker heartbeat")


async def poll_and_record() -> None:
    started = datetime.now(timezone.utc)
    try:
        result = await poll_active_connections()
    except Exception as exc:
        logger.exception("Polling run failed")
        await beat(
            poll=True,
            poll_started_at=started,
            poll_finished_at=datetime.now(timezone.utc),
            error=f"{type(exc).__name__}: {exc}"[:500],
        )
        return
    await beat(
        poll=True,
        poll_started_at=started,
        poll_finished_at=datetime.now(timezone.utc),
        connections=result.connections,
        failures=result.failures,
        error=result.last_error,
    )


async def sync_intervals() -> None:
    try:
        await poll_intervals_connections()
    except Exception:
        logger.exception("Intervals.icu sync run failed")


async def main() -> None:
    configure_logging()
    settings = get_settings()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_and_record,
        "interval",
        minutes=settings.sqorz_poll_interval_minutes,
        jitter=60,
        # A slow poll must not pile up behind itself.
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        sync_intervals,
        "interval",
        minutes=settings.intervals_poll_interval_minutes,
        jitter=120,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(beat, "interval", seconds=60)
    scheduler.start()
    logger.info(
        "Sqorz ingestion worker started (interval=%d min)", settings.sqorz_poll_interval_minutes
    )

    touch_heartbeat_file()
    # Run once immediately on startup, then let the interval trigger take over.
    await poll_and_record()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

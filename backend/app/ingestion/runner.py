import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.ingestion.jobs import poll_active_connections

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingestion.runner")


async def main() -> None:
    settings = get_settings()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_active_connections,
        "interval",
        minutes=settings.sqorz_poll_interval_minutes,
        jitter=60,
    )
    scheduler.start()
    logger.info(
        "Sqorz ingestion worker started (interval=%d min)", settings.sqorz_poll_interval_minutes
    )

    # Run once immediately on startup, then let the interval trigger take over.
    await poll_active_connections()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

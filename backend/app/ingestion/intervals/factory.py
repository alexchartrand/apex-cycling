"""Composition root for the Intervals.icu sync."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ingestion.intervals.client import IntervalsHttpClient
from app.ingestion.intervals.ports import IntervalsClientPort
from app.ingestion.intervals.repositories import SqlAlchemyActivityImporter, SqlAlchemyIntervalsConnectionRepository
from app.ingestion.repositories import SqlAlchemySessionCommitter, SqlAlchemySyncRunRepository
from app.ingestion.intervals.service import IntervalsSyncService


def build_intervals_sync_service(db: AsyncSession, *, client: IntervalsClientPort | None = None) -> IntervalsSyncService:
    settings = get_settings()
    return IntervalsSyncService(
        client=client or IntervalsHttpClient(),
        connection_repo=SqlAlchemyIntervalsConnectionRepository(db),
        run_repo=SqlAlchemySyncRunRepository(db),
        importer=SqlAlchemyActivityImporter(db),
        unit_of_work=SqlAlchemySessionCommitter(db),
        backfill_days=settings.intervals_backfill_days,
        max_downloads=settings.intervals_max_downloads_per_run,
    )

"""Composition root for the Intervals.icu sync."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ingestion.intervals.client import IntervalsHttpClient
from app.ingestion.intervals.ports import IntervalsCalendarPort, IntervalsClientPort
from app.ingestion.intervals.push_repositories import SqlAlchemyPlanPushRepository
from app.ingestion.intervals.push_service import PlanPushService
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


def build_plan_push_service(db: AsyncSession, *, client: IntervalsCalendarPort | None = None) -> PlanPushService:
    return PlanPushService(
        client=client or IntervalsHttpClient(),
        repo=SqlAlchemyPlanPushRepository(db),
        unit_of_work=SqlAlchemySessionCommitter(db),
        batch_size=get_settings().intervals_push_batch_size,
    )

"""Composition root for the Strava sync."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ingestion.repositories import SqlAlchemySessionCommitter, SqlAlchemySyncRunRepository
from app.ingestion.strava.client import StravaHttpClient
from app.ingestion.strava.ports import StravaClientPort
from app.ingestion.strava.repositories import SqlAlchemyStravaActivityStore, SqlAlchemyStravaConnectionRepository
from app.ingestion.strava.service import StravaSyncService


def build_strava_sync_service(db: AsyncSession, *, client: StravaClientPort | None = None) -> StravaSyncService:
    settings = get_settings()
    return StravaSyncService(
        client=client or StravaHttpClient(),
        connection_repo=SqlAlchemyStravaConnectionRepository(db),
        run_repo=SqlAlchemySyncRunRepository(db),
        store=SqlAlchemyStravaActivityStore(db),
        unit_of_work=SqlAlchemySessionCommitter(db),
        backfill_days=settings.strava_backfill_days,
        max_downloads=settings.strava_max_downloads_per_run,
    )

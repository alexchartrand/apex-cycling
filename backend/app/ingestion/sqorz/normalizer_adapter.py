"""Bridges the still-procedural normalizer.py (and the personal-records
recompute and activity linking) into their ports so SqorzIngestionService doesn't need to import
sqlalchemy. normalizer.py
itself remains untouched here; decoupling its internals is a follow-up step.
"""
import uuid
from collections.abc import Collection

from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.fusion_service import sync_session_links
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.training.records_service import recompute_many


class SqlAlchemyNormalizerAdapter:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def normalize(self, payload: dict) -> set[uuid.UUID]:
        return await normalize_snapshot(self._db, payload)


class SqlAlchemyRecordsAdapter:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def recompute(self, athlete_ids: Collection[uuid.UUID]) -> None:
        await recompute_many(self._db, athlete_ids)
        # New laps may complete a session a recording was waiting for.
        await sync_session_links(self._db, athlete_ids)

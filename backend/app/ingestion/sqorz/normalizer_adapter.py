"""Bridges the still-procedural normalizer.py into the SnapshotNormalizerPort
so SqorzIngestionService doesn't need to import sqlalchemy. normalizer.py
itself remains untouched here; decoupling its internals is a follow-up step.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.sqorz.normalizer import normalize_snapshot


class SqlAlchemyNormalizerAdapter:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def normalize(self, payload: dict) -> None:
        await normalize_snapshot(self._db, payload)

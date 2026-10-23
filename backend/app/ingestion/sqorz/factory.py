"""Composition root for sqorz ingestion: the one place concrete
SQLAlchemy-backed implementations are wired into SqorzIngestionService.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.sqorz.client import SqorzHttpClient
from app.ingestion.sqorz.normalizer_adapter import (
    SqlAlchemyFailureNotifier,
    SqlAlchemyNormalizerAdapter,
    SqlAlchemyRecordsAdapter,
)
from app.ingestion.sqorz.ports import SqorzClientPort
from app.ingestion.sqorz.repositories import (
    SqlAlchemyDataSourceConnectionRepository,
    SqlAlchemyIngestionRunRepository,
    SqlAlchemyRawSnapshotRepository,
    SqlAlchemySessionCommitter,
)
from app.ingestion.sqorz.service import SqorzIngestionService


def build_sqorz_ingestion_service(
    db: AsyncSession, *, client: SqorzClientPort | None = None
) -> SqorzIngestionService:
    return SqorzIngestionService(
        client=client or SqorzHttpClient(),
        connection_repo=SqlAlchemyDataSourceConnectionRepository(db),
        run_repo=SqlAlchemyIngestionRunRepository(db),
        snapshot_repo=SqlAlchemyRawSnapshotRepository(db),
        normalizer=SqlAlchemyNormalizerAdapter(db),
        records=SqlAlchemyRecordsAdapter(db),
        unit_of_work=SqlAlchemySessionCommitter(db),
        failure_notifier=SqlAlchemyFailureNotifier(db),
    )

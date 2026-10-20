import hashlib
import json
import uuid

from app.db.base import utcnow
from app.ingestion.sqorz.client import SqorzClientError
from app.ingestion.sqorz.dtos import DataSourceConnectionRecord, IngestionRunRecord
from app.ingestion.sqorz.ports import (
    AthleteRecordsPort,
    DataSourceConnectionRepositoryPort,
    IngestionRunRepositoryPort,
    RawSnapshotRepositoryPort,
    SnapshotNormalizerPort,
    SqorzClientPort,
    UnitOfWorkPort,
)


def _content_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _extract_account_info(payload: dict) -> tuple[str | None, str | None]:
    details = payload.get("eventTrainingDetails") or []
    if not details:
        return None, None
    first = details[0]
    return first.get("accountId"), first.get("accountName")


class SqorzIngestionService:
    """Fetches a transponder's full history, dedupes against the latest
    stored snapshot by content hash, records an IngestionRun, and triggers
    normalization into the query-friendly training tables, then refreshes
    the personal records derived from them.
    """

    def __init__(
        self,
        *,
        client: SqorzClientPort,
        connection_repo: DataSourceConnectionRepositoryPort,
        run_repo: IngestionRunRepositoryPort,
        snapshot_repo: RawSnapshotRepositoryPort,
        normalizer: SnapshotNormalizerPort,
        records: AthleteRecordsPort,
        unit_of_work: UnitOfWorkPort,
    ) -> None:
        self._client = client
        self._connection_repo = connection_repo
        self._run_repo = run_repo
        self._snapshot_repo = snapshot_repo
        self._normalizer = normalizer
        self._records = records
        self._unit_of_work = unit_of_work

    async def ingest(self, connection: DataSourceConnectionRecord) -> IngestionRunRecord:
        run = await self._run_repo.create(connection.id, utcnow())

        try:
            payload = await self._client.fetch_transponder_history(connection.external_id)
        except SqorzClientError as exc:
            run = await self._run_repo.mark_failed(
                run.id, http_status=exc.http_status, error_message=str(exc), completed_at=utcnow()
            )
            await self._unit_of_work.commit()
            return run

        content_hash = _content_hash(payload)

        latest_hash = await self._snapshot_repo.get_latest_hash(connection.external_id)
        if latest_hash != content_hash:
            await self._snapshot_repo.create(
                ingestion_run_id=run.id,
                external_ref=connection.external_id,
                payload=payload,
                content_hash=content_hash,
                fetched_at=utcnow(),
            )

        account_id, account_name = _extract_account_info(payload)
        await self._connection_repo.update_after_sync(
            connection.id,
            sqorz_account_id=account_id,
            sqorz_account_name=account_name,
            last_synced_at=utcnow(),
        )

        # Always re-normalize the freshly fetched payload (even if unchanged from
        # the last snapshot) so a newly-added TransponderAssignment backfills
        # attribution for laps that were previously unattributed.
        athlete_ids = await self._normalizer.normalize(payload)
        await self._records.recompute(athlete_ids)

        run = await self._run_repo.mark_success(run.id, http_status=200, completed_at=utcnow())

        await self._unit_of_work.commit()
        return run

    async def ingest_by_id(self, connection_id: uuid.UUID) -> IngestionRunRecord | None:
        connection = await self._connection_repo.get_by_id(connection_id)
        if connection is None:
            return None
        return await self.ingest(connection)

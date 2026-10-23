import logging
from datetime import timedelta

from app.db.base import utcnow
from app.ingestion.intervals.client import IntervalsAuthError, IntervalsClientError, IntervalsRateLimited
from app.ingestion.intervals.dtos import IntervalsConnectionRecord, RemoteActivity, SyncResult
from app.ingestion.common import SyncRunRepositoryPort, UnitOfWorkPort
from app.ingestion.intervals.ports import (
    ActivityImporterPort,
    ActivityRejected,
    IntervalsClientPort,
    IntervalsConnectionRepositoryPort,
)

logger = logging.getLogger("ingestion.intervals")

# A new sync starts this far before the last one finished, so a ride that was
# still uploading then is picked up.
_OVERLAP = timedelta(days=2)


class IntervalsSyncService:
    """Brings an athlete's Intervals.icu rides and gym sessions into ApexCycling: lists the
    recent activities, skips those already imported, and runs each original
    file through the same import as an upload (so it is parsed, deduped
    against uploads, scored and linked to its sqorz session).

    Strava-sourced activities are skipped: Intervals.icu can't serve them.
    Each activity is committed on its own, and `last_synced_at` only moves
    forward when the run saw everything, so a long history arrives over
    several runs.
    """

    def __init__(
        self,
        *,
        client: IntervalsClientPort,
        connection_repo: IntervalsConnectionRepositoryPort,
        run_repo: SyncRunRepositoryPort,
        importer: ActivityImporterPort,
        unit_of_work: UnitOfWorkPort,
        backfill_days: int,
        max_downloads: int,
    ) -> None:
        self._client = client
        self._connections = connection_repo
        self._runs = run_repo
        self._importer = importer
        self._unit_of_work = unit_of_work
        self._backfill_days = backfill_days
        self._max_downloads = max_downloads

    async def sync(self, connection: IntervalsConnectionRecord) -> SyncResult:
        run_id = await self._runs.create(connection.id, utcnow())
        await self._unit_of_work.commit()
        imported = duplicates = skipped = failed = 0
        complete = False
        http_status: int | None = 200
        error: str | None = None
        try:
            today = utcnow().date()
            oldest = (
                connection.last_synced_at.date() - _OVERLAP
                if connection.last_synced_at
                else today - timedelta(days=self._backfill_days)
            )
            remote = await self._client.list_activities(connection.api_key, oldest, today + timedelta(days=1))
            candidates = [a for a in remote if a.is_wanted and not a.is_strava and not a.has_note]
            known = await self._connections.known_external_ids(connection.id, [a.id for a in candidates])
            pending = sorted((a for a in candidates if a.id not in known), key=lambda a: a.start_local or utcnow(), reverse=True)
            skipped = len(remote) - len(candidates)

            for activity in pending[: self._max_downloads]:
                try:
                    outcome = await self._import(connection, activity)
                except ActivityRejected as exc:
                    failed += 1
                    logger.warning("Intervals.icu activity %s not imported: %s", activity.id, exc)
                    continue
                if outcome is None:
                    skipped += 1
                    continue
                if outcome == "created":
                    imported += 1
                else:
                    duplicates += 1
                await self._unit_of_work.commit()
            complete = len(pending) <= self._max_downloads
            if complete:
                await self._connections.mark_synced(connection.id, utcnow())
        except IntervalsAuthError as exc:
            error, http_status = str(exc), exc.http_status
            await self._unit_of_work.rollback()
            await self._connections.deactivate(connection.id)
        except IntervalsRateLimited as exc:
            error, http_status = f"{exc} (retry in {exc.retry_after_s or '?'} s)", 429
            await self._unit_of_work.rollback()
        except IntervalsClientError as exc:
            error, http_status = str(exc), exc.http_status
            await self._unit_of_work.rollback()
        except Exception as exc:
            # Whatever else went wrong, the run must not stay "pending" forever.
            logger.exception("Intervals.icu sync of connection %s failed", connection.id)
            error, http_status = f"{type(exc).__name__}: {exc}"[:500], None
            await self._unit_of_work.rollback()

        await self._runs.finish(
            run_id,
            success=error is None,
            completed_at=utcnow(),
            http_status=http_status,
            error_message=error,
            imported=imported,
        )
        await self._unit_of_work.commit()
        return SyncResult(
            status="failed" if error else "success",
            imported=imported,
            duplicates=duplicates,
            skipped=skipped,
            failed=failed,
            complete=complete and error is None,
            error=error,
        )

    async def _import(self, connection: IntervalsConnectionRecord, activity: RemoteActivity):
        """Imports from the original file; a gym session without a usable file
        (typed in by hand, or a watch file with no samples) is kept from the
        numbers Intervals.icu has. None when there is nothing to keep."""
        content = await self._client.download_file(connection.api_key, activity.id)
        if content is not None:
            try:
                return await self._importer.import_file(connection, activity, content)
            except ActivityRejected:
                if not activity.is_gym:
                    raise
        elif not activity.is_gym:
            return None
        return await self._importer.import_summary(connection, activity)

    async def sync_by_id(self, connection_id) -> SyncResult | None:
        connection = await self._connections.get_active(connection_id)
        return None if connection is None else await self.sync(connection)

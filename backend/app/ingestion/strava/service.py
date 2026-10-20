import logging
import time
import uuid
from datetime import timedelta

from app.db.base import utcnow
from app.ingestion.common import SyncRunRepositoryPort, UnitOfWorkPort
from app.ingestion.strava.client import StravaAuthError, StravaClientError, StravaRateLimited
from app.ingestion.strava.dtos import StravaConnectionRecord, StravaSyncResult, StravaTokens
from app.ingestion.strava.ports import (
    ActivityRejected,
    StravaActivityStorePort,
    StravaClientPort,
    StravaConnectionRepositoryPort,
)

logger = logging.getLogger("ingestion.strava")

_OVERLAP = timedelta(days=2)
_PAGE_SIZE = 100
_MAX_PAGES = 3
# Tokens last six hours; refresh a little early.
_REFRESH_MARGIN_S = 300


class StravaSyncService:
    """Brings an athlete's Strava rides into ApexCycling as stream data.

    Strava's API terms allow its data to be shown only to the athlete it
    belongs to, so these activities are owner-only everywhere they are read,
    and everything is deleted when the athlete revokes access. A ride the
    athlete already has from another source is not fetched at all: it costs
    API calls (the whole application shares 100 requests / 15 min) and the
    athlete's own file is the better copy.
    """

    def __init__(
        self,
        *,
        client: StravaClientPort,
        connection_repo: StravaConnectionRepositoryPort,
        run_repo: SyncRunRepositoryPort,
        store: StravaActivityStorePort,
        unit_of_work: UnitOfWorkPort,
        backfill_days: int,
        max_downloads: int,
    ) -> None:
        self._client = client
        self._connections = connection_repo
        self._runs = run_repo
        self._store = store
        self._unit_of_work = unit_of_work
        self._backfill_days = backfill_days
        self._max_downloads = max_downloads

    async def _fresh_tokens(self, connection: StravaConnectionRecord) -> StravaTokens:
        tokens = connection.tokens
        if tokens.expires_at - _REFRESH_MARGIN_S > time.time():
            return tokens
        tokens = await self._client.refresh_tokens(tokens.refresh_token)
        # Strava rotates refresh tokens: the new one must be saved before anything else can fail.
        await self._connections.save_tokens(connection.id, tokens)
        await self._unit_of_work.commit()
        return tokens

    async def sync(self, connection: StravaConnectionRecord) -> StravaSyncResult:
        run_id = await self._runs.create(connection.id, utcnow())
        await self._unit_of_work.commit()
        imported = skipped = failed = 0
        complete = rate_limited = False
        http_status: int | None = 200
        error: str | None = None
        try:
            tokens = await self._fresh_tokens(connection)
            now = utcnow()
            after = (connection.last_synced_at or now - timedelta(days=self._backfill_days)) - (
                _OVERLAP if connection.last_synced_at else timedelta()
            )
            remote = []
            for page in range(1, _MAX_PAGES + 1):
                batch = await self._client.list_activities(tokens.access_token, after, now + timedelta(days=1), page)
                remote.extend(batch)
                if len(batch) < _PAGE_SIZE:
                    break
            else:
                logger.info("Strava connection %s has more than %d activities to list", connection.id, _MAX_PAGES * _PAGE_SIZE)

            candidates = [a for a in remote if a.is_ride and not a.manual]
            skipped = len(remote) - len(candidates)
            known = await self._connections.known_external_ids(connection.id, [a.id for a in candidates])
            pending = []
            for activity in sorted((a for a in candidates if a.id not in known), key=lambda a: a.start, reverse=True):
                if await self._store.has_same_ride(connection, activity):
                    skipped += 1
                else:
                    pending.append(activity)

            for activity in pending[: self._max_downloads]:
                streams = await self._client.get_streams(tokens.access_token, activity.id)
                if not streams:
                    skipped += 1
                    continue
                try:
                    await self._store.import_streams(connection, activity, streams)
                except ActivityRejected as exc:
                    failed += 1
                    logger.warning("Strava activity %s not imported: %s", activity.id, exc)
                    continue
                imported += 1
                await self._unit_of_work.commit()
            complete = len(pending) <= self._max_downloads
            if complete:
                await self._connections.mark_synced(connection.id, utcnow())
        except StravaAuthError as exc:
            error, http_status = str(exc), exc.http_status
            await self._unit_of_work.rollback()
            await self._connections.revoke(connection.id)
        except StravaRateLimited as exc:
            error, http_status, rate_limited = str(exc), 429, True
            await self._unit_of_work.rollback()
        except StravaClientError as exc:
            error, http_status = str(exc), exc.http_status
            await self._unit_of_work.rollback()
        except Exception as exc:
            logger.exception("Strava sync of connection %s failed", connection.id)
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
        return StravaSyncResult(
            status="failed" if error else "success",
            imported=imported,
            skipped=skipped,
            failed=failed,
            complete=complete and error is None,
            rate_limited=rate_limited,
            error=error,
        )

    async def sync_by_id(self, connection_id: uuid.UUID) -> StravaSyncResult | None:
        connection = await self._connections.get_active(connection_id)
        return None if connection is None else await self.sync(connection)

    # --- webhook events: hints, verified against Strava before acting ---------------------

    async def handle_activity_deleted(self, strava_athlete_id: str, activity_id: str) -> bool:
        """Strava says an activity was deleted; remove ours if Strava confirms."""
        connection = await self._connections.get_by_strava_athlete(strava_athlete_id)
        if connection is None:
            return False
        try:
            tokens = await self._fresh_tokens(connection)
            if await self._client.activity_exists(tokens.access_token, activity_id):
                return False
        except StravaClientError:
            return False
        await self._store.delete(connection, activity_id)
        await self._unit_of_work.commit()
        return True

    async def handle_deauthorized(self, strava_athlete_id: str) -> bool:
        """Strava says the athlete revoked access; if their tokens really stopped
        working, forget the connection and delete the Strava data."""
        connection = await self._connections.get_by_strava_athlete(strava_athlete_id)
        if connection is None:
            return False
        try:
            await self._fresh_tokens(
                StravaConnectionRecord(
                    connection.id, connection.athlete_id, connection.strava_athlete_id,
                    StravaTokens(connection.tokens.access_token, connection.tokens.refresh_token, 0),
                    connection.last_synced_at,
                )  # fmt: skip
            )
        except StravaAuthError:
            await self._connections.revoke(connection.id)
            await self._unit_of_work.commit()
            return True
        except StravaClientError:
            return False
        return False


"""SQLAlchemy-backed implementations of the Strava sync ports — the only
module of this package that talks to the database."""

import uuid
from collections.abc import Collection
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.models import Activity, ActivitySource
from app.activities.parsers import ActivityParseError
from app.activities.service import delete_activities, find_same_ride, import_parsed_activity
from app.connections.models import DataSourceConnection, DataSourceConnectionStatus, DataSourceProvider
from app.ingestion.strava.dtos import RemoteStravaActivity, StravaConnectionRecord, StravaTokens
from app.ingestion.strava.mapping import to_parsed_activity
from app.ingestion.strava.ports import ActivityRejected


async def purge_strava_data(db: AsyncSession, athlete_id: uuid.UUID) -> int:
    """Deletes every Strava-sourced activity of the athlete. Strava's terms
    require this when access is revoked. Doesn't commit."""
    activities = list(
        await db.scalars(
            select(Activity).where(Activity.athlete_id == athlete_id, Activity.source == ActivitySource.STRAVA)
        )
    )
    await delete_activities(db, activities)
    return len(activities)


def _record(connection: DataSourceConnection) -> StravaConnectionRecord | None:
    credentials = connection.credentials or {}
    if connection.athlete_id is None or not credentials.get("refresh_token"):
        return None
    return StravaConnectionRecord(
        id=connection.id,
        athlete_id=connection.athlete_id,
        strava_athlete_id=connection.external_id,
        tokens=StravaTokens(
            access_token=credentials.get("access_token", ""),
            refresh_token=credentials["refresh_token"],
            expires_at=int(credentials.get("expires_at", 0)),
        ),
        last_synced_at=connection.last_synced_at,
    )


class SqlAlchemyStravaConnectionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_active(self, connection_id: uuid.UUID) -> StravaConnectionRecord | None:
        connection = await self._db.get(DataSourceConnection, connection_id)
        if (
            connection is None
            or connection.provider != DataSourceProvider.STRAVA
            or connection.status != DataSourceConnectionStatus.ACTIVE
        ):
            return None
        return _record(connection)

    async def get_by_strava_athlete(self, strava_athlete_id: str) -> StravaConnectionRecord | None:
        connection = await self._db.scalar(
            select(DataSourceConnection).where(
                DataSourceConnection.provider == DataSourceProvider.STRAVA,
                DataSourceConnection.external_id == strava_athlete_id,
                DataSourceConnection.status == DataSourceConnectionStatus.ACTIVE,
            )
        )
        return None if connection is None else _record(connection)

    async def save_tokens(self, connection_id: uuid.UUID, tokens: StravaTokens) -> None:
        connection = await self._db.get(DataSourceConnection, connection_id)
        # Reassigned as a whole: the column is only written when the value changes.
        connection.credentials = {
            **(connection.credentials or {}),
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": tokens.expires_at,
        }

    async def known_external_ids(self, connection_id: uuid.UUID, candidates: Collection[str]) -> set[str]:
        if not candidates:
            return set()
        rows = await self._db.scalars(
            select(Activity.external_id).where(
                Activity.data_source_connection_id == connection_id, Activity.external_id.in_(list(candidates))
            )
        )
        return set(rows)

    async def mark_synced(self, connection_id: uuid.UUID, at: datetime) -> None:
        connection = await self._db.get(DataSourceConnection, connection_id)
        connection.last_synced_at = at

    async def revoke(self, connection_id: uuid.UUID) -> None:
        connection = await self._db.get(DataSourceConnection, connection_id)
        connection.credentials = None
        connection.status = DataSourceConnectionStatus.INACTIVE
        if connection.athlete_id is not None:
            await purge_strava_data(self._db, connection.athlete_id)


class SqlAlchemyStravaActivityStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def has_same_ride(self, connection: StravaConnectionRecord, remote: RemoteStravaActivity) -> bool:
        return await find_same_ride(self._db, connection.athlete_id, remote.start, remote.elapsed_s) is not None

    async def import_streams(
        self, connection: StravaConnectionRecord, remote: RemoteStravaActivity, streams: dict[str, list]
    ) -> Literal["created", "duplicate"]:
        try:
            parsed = to_parsed_activity(remote, streams)
        except ActivityParseError as exc:
            raise ActivityRejected(str(exc)) from exc
        outcome = await import_parsed_activity(
            self._db,
            connection.athlete_id,
            parsed,
            source=ActivitySource.STRAVA,
            external_id=remote.id,
            data_source_connection_id=connection.id,
        )
        return outcome.status

    async def delete(self, connection: StravaConnectionRecord, activity_id: str) -> None:
        activities = list(
            await self._db.scalars(
                select(Activity).where(
                    Activity.athlete_id == connection.athlete_id,
                    Activity.source == ActivitySource.STRAVA,
                    Activity.external_id == activity_id,
                )
            )
        )
        await delete_activities(self._db, activities)

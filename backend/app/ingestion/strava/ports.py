"""Protocols the Strava sync logic depends on; wired together in factory.py."""

import uuid
from collections.abc import Collection
from datetime import datetime
from typing import Literal, Protocol

from app.ingestion.strava.dtos import AuthorizedAthlete, RemoteStravaActivity, StravaConnectionRecord, StravaTokens


class StravaClientPort(Protocol):
    async def exchange_code(self, code: str) -> AuthorizedAthlete: ...

    async def deauthorize(self, access_token: str) -> None: ...

    async def refresh_tokens(self, refresh_token: str) -> StravaTokens: ...

    async def list_activities(
        self, access_token: str, after: datetime, before: datetime, page: int
    ) -> list[RemoteStravaActivity]: ...

    async def get_streams(self, access_token: str, activity_id: str) -> dict[str, list] | None: ...

    async def activity_exists(self, access_token: str, activity_id: str) -> bool: ...


class StravaConnectionRepositoryPort(Protocol):
    async def get_active(self, connection_id: uuid.UUID) -> StravaConnectionRecord | None: ...

    async def get_by_strava_athlete(self, strava_athlete_id: str) -> StravaConnectionRecord | None: ...

    async def save_tokens(self, connection_id: uuid.UUID, tokens: StravaTokens) -> None: ...

    async def known_external_ids(self, connection_id: uuid.UUID, candidates: Collection[str]) -> set[str]: ...

    async def mark_synced(self, connection_id: uuid.UUID, at: datetime) -> None: ...

    async def revoke(self, connection_id: uuid.UUID) -> None:
        """Strava no longer accepts the connection: forget the tokens, stop
        polling, and delete the Strava data (Strava's terms require it)."""
        ...


class StravaActivityStorePort(Protocol):
    async def has_same_ride(self, connection: StravaConnectionRecord, remote: RemoteStravaActivity) -> bool:
        """The athlete already has this ride (from any source)."""
        ...

    async def import_streams(
        self, connection: StravaConnectionRecord, remote: RemoteStravaActivity, streams: dict[str, list]
    ) -> Literal["created", "duplicate"]:
        """Raises ActivityRejected for streams that make no activity."""
        ...

    async def delete(self, connection: StravaConnectionRecord, activity_id: str) -> None: ...


class ActivityRejected(Exception):
    pass

"""Protocols the Intervals.icu sync logic depends on; concrete versions are
wired together in factory.py. service.py imports only this module."""

import uuid
from collections.abc import Collection
from datetime import date, datetime
from typing import Literal, Protocol

from app.ingestion.intervals.dtos import IntervalsConnectionRecord, RemoteActivity, RemoteAthlete


class ActivityRejected(Exception):
    """The downloaded file isn't a usable activity."""


class IntervalsClientPort(Protocol):
    async def get_athlete(self, api_key: str) -> RemoteAthlete: ...

    async def list_activities(self, api_key: str, oldest: date, newest: date) -> list[RemoteActivity]: ...

    async def download_file(self, api_key: str, activity_id: str) -> bytes | None: ...


class IntervalsConnectionRepositoryPort(Protocol):
    async def get_active(self, connection_id: uuid.UUID) -> IntervalsConnectionRecord | None: ...

    async def known_external_ids(self, connection_id: uuid.UUID, candidates: Collection[str]) -> set[str]: ...

    async def mark_synced(self, connection_id: uuid.UUID, at: datetime) -> None: ...

    async def deactivate(self, connection_id: uuid.UUID) -> None:
        """The key stopped working: stop polling until the athlete reconnects."""
        ...


class ActivityImporterPort(Protocol):
    async def import_file(
        self, connection: IntervalsConnectionRecord, remote: RemoteActivity, content: bytes
    ) -> Literal["created", "duplicate"]:
        """Stores the activity for the connection's athlete. Raises
        `ActivityRejected` for an unusable file."""
        ...

    async def import_summary(
        self, connection: IntervalsConnectionRecord, remote: RemoteActivity
    ) -> Literal["created", "duplicate"]:
        """Stores an activity that has no file, from the numbers Intervals.icu
        gives. Raises `ActivityRejected` when those don't say when it was and
        how long it lasted."""
        ...

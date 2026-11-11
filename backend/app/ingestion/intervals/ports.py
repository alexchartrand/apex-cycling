"""Protocols the Intervals.icu sync logic depends on; concrete versions are
wired together in factory.py. service.py imports only this module."""

import uuid
from collections.abc import Collection
from datetime import date, datetime
from typing import Literal, Protocol

from app.ingestion.intervals.dtos import IntervalsConnectionRecord, PlanPushJob, RemoteActivity, RemoteAthlete


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


class IntervalsCalendarPort(Protocol):
    async def save_event(self, api_key: str, event_id: str | None, event: dict) -> str:
        """Updates the event, or creates it (idempotent on its `uid`); its id."""
        ...

    async def delete_event(self, api_key: str, event_id: str) -> None:
        """Deletes the event we created (its id came back from our create);
        one already gone is fine."""
        ...


class PlanPushRepositoryPort(Protocol):
    async def due(self, now: datetime, limit: int, athlete_id: uuid.UUID | None = None) -> list[PlanPushJob]:
        """Oldest first, only for athletes whose connection is active (only
        that athlete's when given)."""
        ...

    async def mark_sent(self, job_id: uuid.UUID, event_id: str, payload_hash: str) -> None: ...

    async def forget(self, job_id: uuid.UUID) -> None:
        """The event is gone (or never was): stop tracking it."""
        ...

    async def mark_failed(self, job_id: uuid.UUID, error: str, retry_at: datetime | None) -> None:
        """Counts an attempt; None = give up until the plan changes again."""
        ...

    async def postpone(self, job_id: uuid.UUID, until: datetime) -> None:
        """Try again later without counting an attempt (rate limited)."""
        ...

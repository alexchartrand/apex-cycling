"""Plain records crossing the Intervals.icu sync's port boundary."""

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RemoteAthlete:
    id: str
    name: str | None


@dataclass(frozen=True)
class RemoteActivity:
    id: str
    name: str | None
    type: str | None
    source: str | None
    start_local: datetime | None
    # Intervals.icu attaches a note instead of data to activities it cannot serve.
    has_note: bool

    @property
    def is_ride(self) -> bool:
        return "ride" in (self.type or "").lower() or (self.type or "").lower() == "cycling"

    @property
    def is_strava(self) -> bool:
        return (self.source or "").upper() == "STRAVA"


@dataclass(frozen=True)
class IntervalsConnectionRecord:
    id: uuid.UUID
    athlete_id: uuid.UUID
    api_key: str
    last_synced_at: datetime | None


@dataclass(frozen=True)
class SyncResult:
    status: str  # "success" | "failed"
    imported: int
    duplicates: int
    skipped: int
    failed: int
    complete: bool
    error: str | None = None

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
    # What Intervals.icu itself knows about the activity, enough to keep a
    # gym session that has no file (start is UTC, unlike `start_local`).
    start_utc: datetime | None = None
    elapsed_s: float | None = None
    moving_s: float | None = None
    distance_m: float | None = None
    avg_heart_rate: float | None = None
    max_heart_rate: float | None = None
    rpe: int | None = None
    description: str | None = None

    @property
    def is_ride(self) -> bool:
        return "ride" in (self.type or "").lower() or (self.type or "").lower() == "cycling"

    @property
    def is_gym(self) -> bool:
        return (self.type or "").lower() == "weighttraining"

    @property
    def is_wanted(self) -> bool:
        """Rides and gym sessions are what ApexCycling keeps."""
        return self.is_ride or self.is_gym

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

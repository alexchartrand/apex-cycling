"""Plain records crossing the Strava sync's port boundary."""

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StravaTokens:
    access_token: str
    refresh_token: str
    expires_at: int  # epoch seconds


@dataclass(frozen=True)
class StravaAthleteInfo:
    id: str
    name: str | None


@dataclass(frozen=True)
class AuthorizedAthlete:
    """What the OAuth code exchange returns."""

    athlete: StravaAthleteInfo
    tokens: StravaTokens


@dataclass(frozen=True)
class RemoteStravaActivity:
    id: str
    name: str | None
    sport_type: str | None
    start: datetime
    elapsed_s: float
    moving_s: float | None
    # True when the power came from a power meter, not Strava's estimate.
    device_watts: bool
    manual: bool

    @property
    def is_ride(self) -> bool:
        return "ride" in (self.sport_type or "").lower()


@dataclass(frozen=True)
class StravaConnectionRecord:
    id: uuid.UUID
    athlete_id: uuid.UUID
    strava_athlete_id: str
    tokens: StravaTokens
    last_synced_at: datetime | None


@dataclass(frozen=True)
class StravaSyncResult:
    status: str  # "success" | "failed"
    imported: int
    skipped: int
    failed: int
    complete: bool
    rate_limited: bool = False
    error: str | None = None

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class WorkerStatus(BaseModel):
    # "never": no row yet (worker never started); "stale": no beat for
    # STALE_AFTER_SECONDS; "ok" otherwise.
    state: Literal["ok", "stale", "never"]
    started_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_poll_started_at: datetime | None = None
    last_poll_finished_at: datetime | None = None
    last_poll_connections: int | None = None
    last_poll_failures: int | None = None
    last_error: str | None = None


class AdminCounts(BaseModel):
    users: int
    athletes: int
    clubs: int
    active_transponders: int


class AdminUserRow(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    created_at: datetime
    is_active: bool
    is_platform_admin: bool


class FailedRun(BaseModel):
    id: uuid.UUID
    transponder: str
    requested_at: datetime
    http_status: int | None
    error_message: str | None


class AdminOverview(BaseModel):
    worker: WorkerStatus
    counts: AdminCounts
    recent_users: list[AdminUserRow]
    failed_runs: list[FailedRun]

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.notifications.kinds import NotificationKind


class NotificationRead(BaseModel):
    id: uuid.UUID
    kind: NotificationKind
    payload: dict
    created_at: datetime
    read_at: datetime | None


class UnreadCount(BaseModel):
    count: int


class MarkRead(BaseModel):
    """The ids to mark read, or every one when `ids` is omitted."""

    ids: list[uuid.UUID] | None = Field(default=None, max_length=200)


class ChannelPreferences(BaseModel):
    in_app: bool
    push: bool
    email: bool


class PreferencesRead(BaseModel):
    """What the settings page shows: one row per kind, plus what this server
    can actually send (no SMTP, no VAPID keys: those channels do nothing).
    """

    kinds: dict[NotificationKind, ChannelPreferences]
    email_available: bool
    push_available: bool


class PreferencesWrite(BaseModel):
    kinds: dict[NotificationKind, ChannelPreferences]


class PushConfig(BaseModel):
    enabled: bool
    public_key: str | None


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)


class PushSubscriptionWrite(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)
    keys: PushKeys


class PushSubscriptionDelete(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)



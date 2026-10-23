import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One thing a user should hear about. The row is the in-app entry (the
    bell) and also the outbox for push and email: `want_push` / `want_email`
    were decided from the user's preferences when it was created, and the
    worker sends them and sets `delivered_at`. `payload` carries what the
    screens and messages need (names, ids, times) — never a translated text,
    so the bell follows the viewer's language.

    `dedupe_key`, when set, makes the event idempotent per user.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_notification_user_dedupe"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_delivered_at", "delivered_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Whether the bell shows it (the user's in-app preference at the time).
    in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    want_push: Mapped[bool] = mapped_column(Boolean, default=False)
    want_email: Mapped[bool] = mapped_column(Boolean, default=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user's overrides of the per-kind, per-channel defaults
    (`kinds.DEFAULT_PREFERENCES`): `{kind: {"in_app": bool, "push": bool, "email": bool}}`.
    """

    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    prefs: Mapped[dict] = mapped_column(JSON, default=dict)


class PushSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A browser's Web Push endpoint for a user. `p256dh` and `auth` are the
    subscription's keys; the endpoint is unique, so re-subscribing the same
    browser just moves it to whoever is signed in.
    """

    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(String(2048), unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

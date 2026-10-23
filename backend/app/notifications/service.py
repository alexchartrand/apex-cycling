"""Creating notifications, and sending the ones that leave the app.

Producers call `notify` inside their own transaction (it flushes, never
commits), so a notification exists exactly when the thing it announces does.
The worker's `deliver_pending` then pushes and emails the new ones.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.core.mail import mail_enabled, send_email
from app.db.base import utcnow
from app.notifications.kinds import NotificationKind, effective_preferences
from app.notifications.messages import render
from app.notifications.models import Notification, NotificationPreference, PushSubscription
from app.notifications.push import PushResult, PushTarget, push_enabled, send_push

logger = logging.getLogger(__name__)

DELIVERY_BATCH = 100


async def preferences_of(db: AsyncSession, user_id: uuid.UUID) -> dict[str, dict[str, bool]]:
    row = await db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    return effective_preferences(row.prefs if row else None)


async def save_preferences(db: AsyncSession, user_id: uuid.UUID, prefs: dict[str, dict[str, bool]]) -> dict[str, dict[str, bool]]:
    """Stores the whole matrix; doesn't commit."""
    row = await db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    if row is None:
        row = NotificationPreference(user_id=user_id, prefs={})
        db.add(row)
    row.prefs = prefs
    await db.flush()
    return effective_preferences(row.prefs)


async def notify(
    db: AsyncSession,
    user_id: uuid.UUID,
    kind: NotificationKind,
    payload: dict,
    *,
    dedupe_key: str | None = None,
) -> Notification | None:
    """Records a notification for `user_id` in the channels they have on for
    this kind. Returns None when they have every channel off or the event was
    already recorded for them (same `dedupe_key`). Flushes, doesn't commit.
    """
    channels = (await preferences_of(db, user_id))[kind.value]
    if not any(channels.values()):
        return None
    if dedupe_key is not None:
        known = await db.scalar(
            select(Notification.id).where(Notification.user_id == user_id, Notification.dedupe_key == dedupe_key)
        )
        if known is not None:
            return None
    notification = Notification(
        user_id=user_id,
        kind=kind.value,
        payload=payload,
        dedupe_key=dedupe_key,
        in_app=channels["in_app"],
        want_push=channels["push"],
        want_email=channels["email"],
        # Nothing to send out: it is complete as soon as it exists.
        delivered_at=None if (channels["push"] or channels["email"]) else utcnow(),
    )
    db.add(notification)
    await db.flush()
    return notification


async def notify_many(
    db: AsyncSession, user_ids: set[uuid.UUID], kind: NotificationKind, payload: dict, *, dedupe_key: str | None = None
) -> None:
    for user_id in sorted(user_ids, key=str):
        await notify(db, user_id, kind, payload, dedupe_key=dedupe_key)


# --- reading -------------------------------------------------------------------


async def list_for_user(db: AsyncSession, user_id: uuid.UUID, *, limit: int = 30) -> list[Notification]:
    return list(
        await db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id, Notification.in_app.is_(True))
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    )


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.in_app.is_(True), Notification.read_at.is_(None))
        )
        or 0
    )


async def mark_read(db: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> None:
    """Marks the given notifications (or all, with `ids` None) read; doesn't commit."""
    statement = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    if ids is not None:
        statement = statement.where(Notification.id.in_(ids))
    await db.execute(statement)


# --- push subscriptions -------------------------------------------------------


async def save_subscription(
    db: AsyncSession, user_id: uuid.UUID, *, endpoint: str, p256dh: str, auth: str, user_agent: str | None
) -> None:
    """Stores a browser's subscription, taking it over from whoever had it
    before (a shared browser). Doesn't commit.
    """
    row = await db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if row is None:
        row = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        db.add(row)
    row.user_id, row.p256dh, row.auth, row.user_agent = user_id, p256dh, auth, user_agent
    await db.flush()


async def remove_subscription(db: AsyncSession, user_id: uuid.UUID, endpoint: str) -> None:
    await db.execute(
        delete(PushSubscription).where(PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint)
    )


# --- delivery -------------------------------------------------------------------


async def _push_to_user(db: AsyncSession, notification: Notification, locale: str | None) -> None:
    if not push_enabled():
        return
    subscriptions = list(await db.scalars(select(PushSubscription).where(PushSubscription.user_id == notification.user_id)))
    if not subscriptions:
        return
    message = render(notification.kind, notification.payload, locale)
    data = {"title": message.title, "body": message.body, "url": message.url, "tag": str(notification.id)}
    for subscription in subscriptions:
        result = await send_push(PushTarget(subscription.endpoint, subscription.p256dh, subscription.auth), data)
        if result == PushResult.GONE:
            await db.delete(subscription)


async def deliver_pending(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Pushes and emails the notifications that want it and haven't gone out.
    Each is marked delivered whatever happened (a dead device or a mail
    server hiccup must not be retried forever, and the bell has it anyway).
    Commits per notification; returns how many were processed.
    """
    pending = list(
        await db.scalars(
            select(Notification)
            .where(Notification.delivered_at.is_(None))
            .order_by(Notification.created_at)
            .limit(DELIVERY_BATCH)
        )
    )
    for notification in pending:
        user = await db.get(User, notification.user_id)
        if user is not None and user.is_active:
            if notification.want_push:
                await _push_to_user(db, notification, user.locale)
            if notification.want_email and mail_enabled():
                message = render(notification.kind, notification.payload, user.locale)
                await send_email(user.email, message.title, f"{message.body}\n\n{_absolute(message.url)}\n")
        notification.delivered_at = now or utcnow()
        await db.commit()
    return len(pending)


def _absolute(path: str) -> str:
    return f"{get_settings().app_base_url.rstrip('/')}{path}"

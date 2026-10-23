from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.core.config import get_settings
from app.core.mail import mail_enabled
from app.db.session import get_db
from app.notifications import service
from app.notifications.push import push_enabled
from app.notifications.schemas import (
    ChannelPreferences,
    MarkRead,
    NotificationRead,
    PreferencesRead,
    PreferencesWrite,
    PushConfig,
    PushSubscriptionDelete,
    PushSubscriptionWrite,
    UnreadCount,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[NotificationRead]:
    return [NotificationRead.model_validate(row, from_attributes=True) for row in await service.list_for_user(db, user.id)]


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> UnreadCount:
    return UnreadCount(count=await service.unread_count(db, user.id))


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    payload: MarkRead, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await service.mark_read(db, user.id, payload.ids)
    await db.commit()


async def _preferences(db: AsyncSession, user: User) -> PreferencesRead:
    stored = await service.preferences_of(db, user.id)
    return PreferencesRead(
        kinds={kind: ChannelPreferences(**channels) for kind, channels in stored.items()},  # type: ignore[arg-type]
        email_available=mail_enabled(),
        push_available=push_enabled(),
    )


@router.get("/preferences", response_model=PreferencesRead)
async def get_preferences(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> PreferencesRead:
    return await _preferences(db, user)


@router.put("/preferences", response_model=PreferencesRead)
async def put_preferences(
    payload: PreferencesWrite, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> PreferencesRead:
    current = await service.preferences_of(db, user.id)
    for kind, channels in payload.kinds.items():
        current[kind.value] = channels.model_dump()
    await service.save_preferences(db, user.id, current)
    await db.commit()
    return await _preferences(db, user)


@router.get("/push", response_model=PushConfig)
async def push_config(_: User = Depends(get_current_user)) -> PushConfig:
    return PushConfig(enabled=push_enabled(), public_key=get_settings().vapid_public_key if push_enabled() else None)


@router.post("/push/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    payload: PushSubscriptionWrite,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    user_agent: str | None = Header(default=None),
) -> None:
    await service.save_subscription(
        db,
        user.id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=user_agent[:255] if user_agent else None,
    )
    await db.commit()


@router.post("/push/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    payload: PushSubscriptionDelete, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await service.remove_subscription(db, user.id, payload.endpoint)
    await db.commit()

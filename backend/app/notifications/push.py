"""Web Push delivery (VAPID, via pywebpush). Off unless a key pair is set."""

import asyncio
import json
import logging
from dataclasses import dataclass

from pywebpush import WebPushException, webpush

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# How long a push service may hold a message for a device that is offline.
PUSH_TTL_SECONDS = 24 * 60 * 60


def push_enabled(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.vapid_public_key and settings.vapid_private_key)


@dataclass(frozen=True)
class PushTarget:
    endpoint: str
    p256dh: str
    auth: str


class PushResult:
    SENT = "sent"
    GONE = "gone"  # the subscription is dead and should be forgotten
    FAILED = "failed"  # transient; the endpoint stays


def _send_sync(target: PushTarget, data: dict, settings: Settings) -> str:
    try:
        webpush(
            subscription_info={"endpoint": target.endpoint, "keys": {"p256dh": target.p256dh, "auth": target.auth}},
            data=json.dumps(data),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject or f"mailto:{settings.smtp_from or 'admin@localhost'}"},
            ttl=PUSH_TTL_SECONDS,
            timeout=15,
        )
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            return PushResult.GONE
        logger.warning("Web Push to %s failed: %s", target.endpoint[:60], exc)
        return PushResult.FAILED
    except Exception:
        logger.exception("Web Push to %s failed", target.endpoint[:60])
        return PushResult.FAILED
    return PushResult.SENT


async def send_push(target: PushTarget, data: dict) -> str:
    """Sends one push; returns a `PushResult`. Never raises."""
    settings = get_settings()
    if not push_enabled(settings):
        return PushResult.FAILED
    return await asyncio.to_thread(_send_sync, target, data, settings)

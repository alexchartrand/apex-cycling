"""Who may use the AI coach, and how much.

Only the athlete themself (managed athletes have no login to consent or
chat with), once a platform admin enabled it and the athlete consented to
their data going to the model provider, and while this calendar month's
tokens are under the cap.
"""

import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import get_current_user
from app.auth.models import User
from app.coach_ai.client import ai_coach_available
from app.coach_ai.models import AiCoachAccess, AiUsage
from app.core.config import get_settings
from app.db.session import get_db


class CapReached(Exception):
    """This month's tokens are spent."""


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def access_row(db: AsyncSession, athlete_id: uuid.UUID) -> AiCoachAccess | None:
    return await db.scalar(select(AiCoachAccess).where(AiCoachAccess.athlete_id == athlete_id))


def cap_of(access: AiCoachAccess | None) -> int:
    if access is not None and access.monthly_token_cap:
        return access.monthly_token_cap
    return get_settings().ai_coach_default_monthly_tokens


async def month_tokens(db: AsyncSession, athlete_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.coalesce(func.sum(AiUsage.prompt_tokens + AiUsage.completion_tokens), 0)).where(
                AiUsage.athlete_id == athlete_id, AiUsage.created_at >= month_start()
            )
        )
        or 0
    )


async def check_cap(db: AsyncSession, athlete_id: uuid.UUID) -> None:
    """Raises `CapReached`."""
    if await month_tokens(db, athlete_id) >= cap_of(await access_row(db, athlete_id)):
        raise CapReached


def is_usable(access: AiCoachAccess | None) -> bool:
    return ai_coach_available() and access is not None and access.enabled and access.consent_at is not None


async def _self_athlete(athlete_id: uuid.UUID, user: User, db: AsyncSession) -> tuple[Athlete, AiCoachAccess | None]:
    athlete = await db.get(Athlete, athlete_id)
    if athlete is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Athlete not found")
    if athlete.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the athlete talks to their AI coach")
    if not ai_coach_available():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ai_coach_unavailable")
    access = await access_row(db, athlete.id)
    if access is None or not access.enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ai_coach_not_enabled")
    return athlete, access


async def require_ai_enabled(
    athlete_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Athlete:
    """The athlete themself, enabled by an admin (consent not needed yet:
    this is the gate of the consent route itself)."""
    athlete, _ = await _self_athlete(athlete_id, current_user, db)
    return athlete


async def require_ai_coach(
    athlete_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Athlete:
    """The athlete themself, enabled and consented. The cap is checked
    before each model call (`CapReached`), not here, so history stays
    readable once it is reached."""
    athlete, access = await _self_athlete(athlete_id, current_user, db)
    if access is None or access.consent_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ai_coach_no_consent")
    return athlete


def cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    settings = get_settings()
    return round(
        prompt_tokens / 1e6 * settings.mistral_price_input_per_mtok
        + completion_tokens / 1e6 * settings.mistral_price_output_per_mtok,
        4,
    )

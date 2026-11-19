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
from app.coach_ai.providers import ai_coach_available, current_provider, prices_for_model
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


def has_consent(access: AiCoachAccess | None) -> bool:
    """Consent counts for the provider it was given to only."""
    return access is not None and access.consent_at is not None and access.consent_provider == current_provider()


def is_usable(access: AiCoachAccess | None) -> bool:
    return ai_coach_available() and access is not None and access.enabled and has_consent(access)


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
    if not has_consent(access):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ai_coach_no_consent")
    return athlete


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
    """`prompt_tokens` is every input token, the cached ones included."""
    input_price, output_price, read_price, write_price = prices_for_model(model)
    uncached = max(0, prompt_tokens - cache_read - cache_write)
    return (
        uncached * input_price + cache_read * read_price + cache_write * write_price + completion_tokens * output_price
    ) / 1e6


async def month_usage(db: AsyncSession, athlete_ids: list[uuid.UUID] | None = None) -> dict[uuid.UUID, tuple[int, float]]:
    """This month's (tokens, cost in USD) per athlete, each model at its own prices."""
    query = (
        select(
            AiUsage.athlete_id,
            AiUsage.model,
            func.sum(AiUsage.prompt_tokens),
            func.sum(AiUsage.completion_tokens),
            func.sum(AiUsage.cache_read_tokens),
            func.sum(AiUsage.cache_write_tokens),
        )
        .where(AiUsage.created_at >= month_start())
        .group_by(AiUsage.athlete_id, AiUsage.model)
    )
    if athlete_ids is not None:
        query = query.where(AiUsage.athlete_id.in_(athlete_ids))
    out: dict[uuid.UUID, tuple[int, float]] = {}
    for athlete_id, model, prompt, completion, read, write in (await db.execute(query)).all():
        prompt, completion, read, write = (int(v or 0) for v in (prompt, completion, read, write))
        tokens, cost = out.get(athlete_id, (0, 0.0))
        out[athlete_id] = (tokens + prompt + completion, cost + cost_usd(model, prompt, completion, read, write))
    return out

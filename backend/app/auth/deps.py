import uuid

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus
from app.auth.models import User
from app.clubs.models import ClubMembership, ClubRole
from app.core.security import (
    ACCESS_COOKIE_NAME,
    InvalidTokenError,
    TokenType,
    decode_token,
    issued_before_credentials_change,
)
from app.db.session import get_db


async def get_current_user(
    tt_access: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    if tt_access is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        claims = decode_token(tt_access, TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    user = await db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    if issued_before_credentials_change(claims.issued_at, user.credentials_changed_at):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session ended by a password change")
    return user


async def require_athlete_access(
    athlete_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Athlete:
    """Allows access if the current user IS the athlete (via `athletes.user_id`),
    has an ACTIVE `coach_athletes` link to them, or is a `club_admin` of the
    athlete's club. Route path parameter must be named `athlete_id`.
    """
    athlete = await db.get(Athlete, athlete_id)
    if athlete is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Athlete not found")

    if athlete.user_id == current_user.id:
        return athlete

    coach_link = await db.scalar(
        select(CoachAthlete).where(
            CoachAthlete.coach_user_id == current_user.id,
            CoachAthlete.athlete_id == athlete.id,
            CoachAthlete.status == CoachAthleteStatus.ACTIVE,
        )
    )
    if coach_link is not None:
        return athlete

    if athlete.club_id is not None:
        membership = await db.scalar(
            select(ClubMembership).where(
                ClubMembership.user_id == current_user.id,
                ClubMembership.club_id == athlete.club_id,
                ClubMembership.role == ClubRole.CLUB_ADMIN,
            )
        )
        if membership is not None:
            return athlete

    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this athlete")


async def require_club_admin(
    club_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClubMembership:
    membership = await db.scalar(
        select(ClubMembership).where(
            ClubMembership.user_id == current_user.id,
            ClubMembership.club_id == club_id,
            ClubMembership.role == ClubRole.CLUB_ADMIN,
        )
    )
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Club admin access required")
    return membership

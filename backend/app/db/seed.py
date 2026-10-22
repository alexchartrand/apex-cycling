"""Populate a dev database with a representative club/coach/athlete roster.

Usage (from backend/, with DATABASE_URL pointing at a running dev DB):
    python -m app.db.seed
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.models  # noqa: F401 -- registers all models on Base.metadata
from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus, on_roster_of
from app.auth.models import User
from app.clubs.models import Club, ClubMembership, ClubRole
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal

DEV_PASSWORD = "devpassword123"


def _ensure_not_production() -> None:
    # cookie_secure is true only in a production-configured deployment (see
    # docker-compose.prod.yml); refuse to plant well-known dev credentials
    # into a database that's configured that way.
    if get_settings().cookie_secure:
        raise SystemExit(
            "Refusing to run db seed: COOKIE_SECURE is true, which indicates a "
            "production-configured deployment. Seed is dev-only."
        )


async def _get_or_create_user(session: AsyncSession, email: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    user = User(email=email, hashed_password=hash_password(DEV_PASSWORD))
    session.add(user)
    await session.flush()
    return user


async def seed() -> None:
    _ensure_not_production()
    async with AsyncSessionLocal() as session:
        club = await session.scalar(select(Club).where(Club.slug == "cncb"))
        if club is None:
            club = Club(name="CNCB", slug="cncb", timezone="America/Toronto")
            session.add(club)
            await session.flush()

        admin_user = await _get_or_create_user(session, "admin@example.com")
        coach_user = await _get_or_create_user(session, "coach@example.com")
        athlete_user = await _get_or_create_user(session, "athlete@example.com")

        # Each user already got a self-athlete row via signup in the real
        # flow; here we create it directly since we're bypassing /auth/signup.
        for user, display_name in (
            (admin_user, "Admin Person"),
            (coach_user, "Coach Person"),
            (athlete_user, "Athlete Person"),
        ):
            existing = await session.scalar(select(Athlete).where(Athlete.user_id == user.id))
            if existing is None:
                session.add(Athlete(user_id=user.id, display_name=display_name))
        await session.flush()

        athlete_user_athlete = await session.scalar(select(Athlete).where(Athlete.user_id == athlete_user.id))
        athlete_user_athlete.join_club(club.id)

        junior = await session.scalar(
            select(Athlete).where(Athlete.display_name == "Junior Athlete", on_roster_of([club.id]))
        )
        if junior is None:
            junior = Athlete(user_id=None, display_name="Junior Athlete")
            junior.join_club(club.id)
            session.add(junior)
            await session.flush()

        for user_id, role in ((admin_user.id, ClubRole.CLUB_ADMIN), (coach_user.id, ClubRole.COACH)):
            existing_membership = await session.scalar(
                select(ClubMembership).where(ClubMembership.user_id == user_id, ClubMembership.club_id == club.id)
            )
            if existing_membership is None:
                session.add(ClubMembership(user_id=user_id, club_id=club.id, role=role))

        athlete_membership = await session.scalar(
            select(ClubMembership).where(
                ClubMembership.user_id == athlete_user.id, ClubMembership.club_id == club.id
            )
        )
        if athlete_membership is None:
            session.add(ClubMembership(user_id=athlete_user.id, club_id=club.id, role=ClubRole.ATHLETE))

        for athlete_id in (athlete_user_athlete.id, junior.id):
            existing_link = await session.scalar(
                select(CoachAthlete).where(
                    CoachAthlete.coach_user_id == coach_user.id, CoachAthlete.athlete_id == athlete_id
                )
            )
            if existing_link is None:
                session.add(
                    CoachAthlete(
                        coach_user_id=coach_user.id,
                        athlete_id=athlete_id,
                        initiated_by_user_id=coach_user.id,
                        status=CoachAthleteStatus.ACTIVE,
                    )
                )

        await session.commit()

    print("Seed complete. Dev accounts (all use password: %s)" % DEV_PASSWORD)
    print("  admin@example.com   -- club_admin for CNCB")
    print("  coach@example.com   -- coach for CNCB, linked to athlete@example.com and Junior Athlete")
    print("  athlete@example.com -- self-serve athlete, also a CNCB roster member")


if __name__ == "__main__":
    asyncio.run(seed())

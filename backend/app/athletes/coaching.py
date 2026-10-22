"""Coach–athlete links: who may see and work on an athlete's data.

A link needs both sides' consent. Whoever asks creates it pending on the
other side (`PENDING_ATHLETE_ACCEPTANCE` when a coach asks,
`PENDING_COACH_ACCEPTANCE` when the athlete does); the other side accepts, or
declines/cancels (both end as `REVOKED`), and either side can revoke an active
link later. If each side has asked the other, the link just becomes active.

An athlete with a login speaks for themself. A managed athlete (no login) is
spoken for by their club's admins — the one case where a link is activated
without anyone consenting on the athlete's side, because there is nobody to.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus, on_roster_of
from app.athletes.schemas import CoachLinkRead
from app.auth.models import User
from app.clubs.models import ClubMembership, ClubRole

PENDING = (CoachAthleteStatus.PENDING_ATHLETE_ACCEPTANCE, CoachAthleteStatus.PENDING_COACH_ACCEPTANCE)
OPEN = (*PENDING, CoachAthleteStatus.ACTIVE)


class CoachLinkError(Exception):
    """A request that's well-formed but not possible in the link's current
    state (router: 409)."""


class NotAllowed(Exception):
    """The caller isn't entitled to make this request (router: 403)."""


async def has_club_role(
    db: AsyncSession, user_id: uuid.UUID, athlete: Athlete, roles: tuple[ClubRole, ...]
) -> bool:
    """Whether the user holds one of `roles` in any club the athlete is on the roster of."""
    if not athlete.club_ids:
        return False
    found = await db.scalar(
        select(ClubMembership.id)
        .where(
            ClubMembership.user_id == user_id,
            ClubMembership.club_id.in_(athlete.club_ids),
            ClubMembership.role.in_(roles),
        )
        .limit(1)
    )
    return found is not None


async def admin_club_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await db.scalars(
        select(ClubMembership.club_id).where(
            ClubMembership.user_id == user_id, ClubMembership.role == ClubRole.CLUB_ADMIN
        )
    )
    return set(rows)


def _speaks_for(user_id: uuid.UUID, admin_clubs: set[uuid.UUID], athlete: Athlete) -> bool:
    if athlete.user_id is not None:
        return athlete.user_id == user_id
    return any(club_id in admin_clubs for club_id in athlete.club_ids)


async def speaks_for_athlete(db: AsyncSession, user: User, athlete: Athlete) -> bool:
    return _speaks_for(user.id, await admin_club_ids(db, user.id), athlete)


async def self_athlete(db: AsyncSession, user_id: uuid.UUID) -> Athlete | None:
    return await db.scalar(select(Athlete).where(Athlete.user_id == user_id))


# --- asking ----------------------------------------------------------------


async def _open_link(
    db: AsyncSession, *, coach_user_id: uuid.UUID, athlete: Athlete, status: CoachAthleteStatus, actor: User
) -> CoachAthlete:
    """Creates the link in `status`, or moves an existing one on: asking
    again is a no-op, asking back activates, asking after a revocation
    reopens it."""
    if coach_user_id == athlete.user_id:
        raise CoachLinkError("Nobody coaches themself")
    now = datetime.now(timezone.utc)
    link = await db.scalar(
        select(CoachAthlete).where(CoachAthlete.coach_user_id == coach_user_id, CoachAthlete.athlete_id == athlete.id)
    )
    if link is None:
        link = CoachAthlete(
            coach_user_id=coach_user_id, athlete_id=athlete.id, initiated_by_user_id=actor.id, status=status
        )
        if status == CoachAthleteStatus.ACTIVE:
            link.responded_at = now
        db.add(link)
    elif link.status == CoachAthleteStatus.ACTIVE:
        raise CoachLinkError("Already linked")
    elif link.status == CoachAthleteStatus.REVOKED:
        link.status, link.initiated_by_user_id = status, actor.id
        link.responded_at = now if status == CoachAthleteStatus.ACTIVE else None
    elif link.status != status:  # the other side had already asked: both want it
        link.status, link.responded_at = CoachAthleteStatus.ACTIVE, now
    await db.flush()
    return link


async def request_as_coach(db: AsyncSession, coach: User, athlete: Athlete) -> CoachAthlete:
    """`coach` asks to coach `athlete`."""
    return await _open_link(
        db, coach_user_id=coach.id, athlete=athlete, status=CoachAthleteStatus.PENDING_ATHLETE_ACCEPTANCE, actor=coach
    )


async def request_as_athlete(db: AsyncSession, actor: User, athlete: Athlete, coach_user_id: uuid.UUID) -> CoachAthlete:
    """`actor`, who speaks for `athlete`, asks `coach_user_id` to coach them.
    For a managed athlete the club's admin assigns one of the club's own
    coaches directly."""
    if athlete.user_id is None:
        if not await has_club_role(db, coach_user_id, athlete, (ClubRole.COACH, ClubRole.CLUB_ADMIN)):
            raise NotAllowed("A managed athlete can only be given a coach of their own club")
        status = CoachAthleteStatus.ACTIVE
    else:
        status = CoachAthleteStatus.PENDING_COACH_ACCEPTANCE
    return await _open_link(db, coach_user_id=coach_user_id, athlete=athlete, status=status, actor=actor)


# --- answering ---------------------------------------------------------------


async def _get_involved(db: AsyncSession, link_id: uuid.UUID, user: User) -> tuple[CoachAthlete, bool, bool]:
    """(link, user is the coach, user speaks for the athlete). Raises
    LookupError when the link doesn't exist or has nothing to do with the
    user, so a stranger can't tell the two apart."""
    link = await db.get(CoachAthlete, link_id)
    athlete = await db.get(Athlete, link.athlete_id) if link else None
    if link is None or athlete is None:
        raise LookupError
    is_coach = link.coach_user_id == user.id
    is_athlete_side = await speaks_for_athlete(db, user, athlete)
    if not (is_coach or is_athlete_side):
        raise LookupError
    return link, is_coach, is_athlete_side


async def accept(db: AsyncSession, link_id: uuid.UUID, user: User) -> CoachAthlete:
    link, is_coach, is_athlete_side = await _get_involved(db, link_id, user)
    awaited = {
        CoachAthleteStatus.PENDING_ATHLETE_ACCEPTANCE: is_athlete_side,
        CoachAthleteStatus.PENDING_COACH_ACCEPTANCE: is_coach,
    }.get(link.status)
    if awaited is None:
        raise CoachLinkError("There is no request to accept")
    if not awaited:
        raise NotAllowed("This request is waiting for the other person")
    link.status, link.responded_at = CoachAthleteStatus.ACTIVE, datetime.now(timezone.utc)
    await db.flush()
    return link


async def revoke(db: AsyncSession, link_id: uuid.UUID, user: User) -> CoachAthlete:
    """Ends a link from either side: revokes an active one, or declines or
    cancels a pending one."""
    link, _, _ = await _get_involved(db, link_id, user)
    if link.status != CoachAthleteStatus.REVOKED:
        link.status, link.responded_at = CoachAthleteStatus.REVOKED, datetime.now(timezone.utc)
        await db.flush()
    return link


# --- listing -----------------------------------------------------------------


@dataclass(frozen=True)
class _Row:
    link: CoachAthlete
    athlete: Athlete
    coach_name: str | None


def _read(row: _Row, user: User, admin_clubs: set[uuid.UUID]) -> CoachLinkRead:
    link, athlete = row.link, row.athlete
    if link.status == CoachAthleteStatus.PENDING_COACH_ACCEPTANCE:
        needs_response = link.coach_user_id == user.id
    elif link.status == CoachAthleteStatus.PENDING_ATHLETE_ACCEPTANCE:
        needs_response = _speaks_for(user.id, admin_clubs, athlete)
    else:
        needs_response = False
    return CoachLinkRead(
        id=link.id,
        status=link.status,
        athlete_id=athlete.id,
        athlete_name=athlete.display_name,
        coach_user_id=link.coach_user_id,
        coach_name=row.coach_name,
        initiated_by_me=link.initiated_by_user_id == user.id,
        needs_my_response=needs_response,
        created_at=link.created_at,
        responded_at=link.responded_at,
    )


async def _rows(db: AsyncSession, *conditions) -> list[_Row]:
    coach_profile = aliased(Athlete)
    result = await db.execute(
        select(CoachAthlete, Athlete, coach_profile.display_name)
        .join(Athlete, Athlete.id == CoachAthlete.athlete_id)
        .outerjoin(coach_profile, coach_profile.user_id == CoachAthlete.coach_user_id)
        .where(CoachAthlete.status.in_(OPEN), *conditions)
        .order_by(CoachAthlete.created_at.desc())
    )
    return [_Row(link, athlete, name) for link, athlete, name in result.all()]


async def my_athletes(db: AsyncSession, user: User) -> list[CoachLinkRead]:
    """Links where I'm the coach (active and waiting)."""
    rows = await _rows(db, CoachAthlete.coach_user_id == user.id)
    admin_clubs = await admin_club_ids(db, user.id)
    return [_read(r, user, admin_clubs) for r in rows]


async def coaches_of(db: AsyncSession, user: User, athlete: Athlete) -> list[CoachLinkRead]:
    """Links of one athlete's coaches (active and waiting)."""
    rows = await _rows(db, CoachAthlete.athlete_id == athlete.id)
    admin_clubs = await admin_club_ids(db, user.id)
    return [_read(r, user, admin_clubs) for r in rows]


async def inbox(db: AsyncSession, user: User) -> list[CoachLinkRead]:
    """Every request waiting for me: as a coach, as an athlete, or as an
    admin for a managed athlete."""
    admin_clubs = await admin_club_ids(db, user.id)
    mine = or_(
        CoachAthlete.coach_user_id == user.id,
        Athlete.user_id == user.id,
        and_(Athlete.user_id.is_(None), on_roster_of(admin_clubs)),
    )
    rows = await _rows(db, CoachAthlete.status.in_(PENDING), mine)
    reads = [_read(r, user, admin_clubs) for r in rows]
    return [r for r in reads if r.needs_my_response]


# --- finding the other person ------------------------------------------------


async def athlete_for_email(db: AsyncSession, email: str) -> Athlete | None:
    user = await db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    return await self_athlete(db, user.id) if user else None


async def user_for_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))


async def shares_club_with_coach(db: AsyncSession, viewer_id: uuid.UUID, coach_user_id: uuid.UUID) -> bool:
    """Whether `coach_user_id` is a coach or admin of a club `viewer_id` is in."""
    theirs = aliased(ClubMembership)
    found = await db.scalar(
        select(ClubMembership.id)
        .join(theirs, theirs.club_id == ClubMembership.club_id)
        .where(
            ClubMembership.user_id == viewer_id,
            theirs.user_id == coach_user_id,
            theirs.role.in_((ClubRole.COACH, ClubRole.CLUB_ADMIN)),
        )
        .limit(1)
    )
    return found is not None


async def read_one(db: AsyncSession, link: CoachAthlete, user: User) -> CoachLinkRead:
    [row] = await _rows(db, CoachAthlete.id == link.id)
    return _read(row, user, await admin_club_ids(db, user.id))

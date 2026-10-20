import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes import coaching
from app.athletes.coaching import CoachLinkError, NotAllowed
from app.athletes.dashboard import AthleteCard, coach_dashboard
from app.athletes.models import Athlete
from app.athletes.schemas import CoachLinkRead, CoachLinkRequest, CoachLinkRequested
from app.auth.deps import get_current_user
from app.auth.models import User
from app.clubs.models import ClubRole
from app.core.rate_limit import limiter
from app.db.session import get_db

router = APIRouter(prefix="/coach-links", tags=["coaching"])

_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")


@router.post("", response_model=CoachLinkRequested, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("20/minute")
async def request_link(
    request: Request,
    payload: CoachLinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoachLinkRequested:
    """Asks for a coach–athlete link (see `athletes/coaching.py`). Picking
    someone from a club answers with the real errors; an email request
    answers the same whatever happens, so it can't be used to find out which
    addresses have accounts."""
    by_email = payload.athlete_email is not None or payload.coach_email is not None
    try:
        if payload.acting_as == "coach":
            athlete = await _athlete_to_coach(db, current_user, payload)
            if athlete is not None:
                await coaching.request_as_coach(db, current_user, athlete)
        else:
            athlete = await _athlete_i_speak_for(db, current_user, payload.athlete_id)
            coach_user_id = await _coach_to_ask(db, current_user, payload)
            if coach_user_id is not None:
                await coaching.request_as_athlete(db, current_user, athlete, coach_user_id)
    except (CoachLinkError, NotAllowed) as exc:
        await db.rollback()
        if not by_email:
            code = status.HTTP_409_CONFLICT if isinstance(exc, CoachLinkError) else status.HTTP_403_FORBIDDEN
            raise HTTPException(code, str(exc)) from None
        return CoachLinkRequested()
    await db.commit()
    return CoachLinkRequested()


async def _athlete_to_coach(db: AsyncSession, user: User, payload: CoachLinkRequest) -> Athlete | None:
    if payload.athlete_email is not None:
        return await coaching.athlete_for_email(db, payload.athlete_email)
    athlete = await db.get(Athlete, payload.athlete_id)
    # The club roster is what a coach can browse; anything else is invisible.
    if athlete is None or await coaching.club_role(db, user.id, athlete.club_id) not in (
        ClubRole.COACH,
        ClubRole.CLUB_ADMIN,
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Athlete not found")
    return athlete


async def _athlete_i_speak_for(db: AsyncSession, user: User, athlete_id: uuid.UUID | None) -> Athlete:
    athlete = await db.get(Athlete, athlete_id) if athlete_id else await coaching.self_athlete(db, user.id)
    if athlete is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Athlete not found")
    if not await coaching.speaks_for_athlete(db, user, athlete):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this athlete")
    return athlete


async def _coach_to_ask(db: AsyncSession, user: User, payload: CoachLinkRequest) -> uuid.UUID | None:
    if payload.coach_email is not None:
        coach = await coaching.user_for_email(db, payload.coach_email)
        return coach.id if coach else None
    if not await coaching.shares_club_with_coach(db, user.id, payload.coach_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Coach not found")
    return payload.coach_user_id


@router.get("/athletes", response_model=list[CoachLinkRead])
async def my_athletes(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[CoachLinkRead]:
    """The athletes I coach, and requests to coach them that are still open."""
    return await coaching.my_athletes(db, current_user)


@router.get("/coaches", response_model=list[CoachLinkRead])
async def my_coaches(
    athlete_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CoachLinkRead]:
    """The coaches of me (or of a managed athlete I run), and open requests."""
    athlete = await _athlete_i_speak_for(db, current_user, athlete_id)
    return await coaching.coaches_of(db, current_user, athlete)


@router.get("/inbox", response_model=list[CoachLinkRead])
async def inbox(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[CoachLinkRead]:
    """Requests waiting for my answer, as coach or as athlete."""
    return await coaching.inbox(db, current_user)


@router.get("/dashboard", response_model=list[AthleteCard])
async def dashboard(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[AthleteCard]:
    """One summary card per athlete I actively coach."""
    return await coach_dashboard(db, current_user)


@router.post("/{link_id}/accept", response_model=CoachLinkRead)
async def accept_link(
    link_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> CoachLinkRead:
    try:
        link = await coaching.accept(db, link_id, current_user)
    except LookupError:
        raise _NOT_FOUND from None
    except CoachLinkError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except NotAllowed as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    await db.commit()
    return await coaching.read_one(db, link, current_user)


@router.post("/{link_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_link(
    link_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Response:
    """Ends the link from either side: revokes an active one, declines a
    request made to me, or cancels one I made."""
    try:
        await coaching.revoke(db, link_id, current_user)
    except LookupError:
        raise _NOT_FOUND from None
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

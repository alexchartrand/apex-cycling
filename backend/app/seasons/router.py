import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.coaching import speaks_for_athlete
from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.seasons import service
from app.seasons.schemas import (
    CalendarFeedStatus,
    CompetitionRead,
    CompetitionUpdate,
    CompetitionWrite,
    SeasonRead,
    SeasonSummary,
    SeasonUpdate,
    SeasonWrite,
)

router = APIRouter(prefix="/athletes/{athlete_id}", tags=["seasons"])
public_router = APIRouter(tags=["seasons"])

_NO_SEASON = HTTPException(status.HTTP_404_NOT_FOUND, "Season not found")
_NO_COMPETITION = HTTPException(status.HTTP_404_NOT_FOUND, "Competition not found")
_NO_GOAL = HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
_SEASON_EXISTS = HTTPException(status.HTTP_409_CONFLICT, "There is already a season starting that day")


# --- seasons -----------------------------------------------------------------------------


@router.get("/seasons", response_model=list[SeasonRead])
async def list_seasons(
    athlete: Athlete = Depends(require_athlete_access), db: AsyncSession = Depends(get_db)
) -> list[SeasonRead]:
    """Newest first. A season runs until the day before the next one starts."""
    return await service.list_seasons(db, athlete)


@router.post("/seasons", response_model=SeasonRead, status_code=status.HTTP_201_CREATED)
async def create_season(
    payload: SeasonWrite, athlete: Athlete = Depends(require_athlete_access), db: AsyncSession = Depends(get_db)
) -> SeasonRead:
    try:
        return await service.create_season(db, athlete, payload)
    except service.DuplicateSeason:
        raise _SEASON_EXISTS from None


@router.get("/seasons/{season_id}", response_model=SeasonSummary)
async def season_summary(
    season_id: uuid.UUID, athlete: Athlete = Depends(require_athlete_access), db: AsyncSession = Depends(get_db)
) -> SeasonSummary:
    """The season with its bests per place, event and start, against what the athlete had before."""
    summary = await service.season_summary(db, athlete, season_id)
    if summary is None:
        raise _NO_SEASON
    return summary


@router.patch("/seasons/{season_id}", response_model=SeasonRead)
async def update_season(
    season_id: uuid.UUID,
    payload: SeasonUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> SeasonRead:
    try:
        updated = await service.update_season(db, athlete, season_id, payload)
    except service.DuplicateSeason:
        raise _SEASON_EXISTS from None
    if updated is None:
        raise _NO_SEASON
    return updated


@router.delete("/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_season(
    season_id: uuid.UUID, athlete: Athlete = Depends(require_athlete_access), db: AsyncSession = Depends(get_db)
) -> Response:
    if not await service.delete_season(db, athlete.id, season_id):
        raise _NO_SEASON
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- competitions ---------------------------------------------------------------------------


@router.get("/competitions", response_model=list[CompetitionRead])
async def list_competitions(
    athlete: Athlete = Depends(require_athlete_access), db: AsyncSession = Depends(get_db)
) -> list[CompetitionRead]:
    """Coming races soonest first, then the past ones."""
    return await service.list_competitions(db, athlete)


@router.post("/competitions", response_model=CompetitionRead, status_code=status.HTTP_201_CREATED)
async def create_competition(
    payload: CompetitionWrite, athlete: Athlete = Depends(require_athlete_access), db: AsyncSession = Depends(get_db)
) -> CompetitionRead:
    try:
        return await service.create_competition(db, athlete, payload)
    except service.UnknownGoal:
        raise _NO_GOAL from None


@router.patch("/competitions/{competition_id}", response_model=CompetitionRead)
async def update_competition(
    competition_id: uuid.UUID,
    payload: CompetitionUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> CompetitionRead:
    try:
        updated = await service.update_competition(db, athlete, competition_id, payload)
    except service.UnknownGoal:
        raise _NO_GOAL from None
    if updated is None:
        raise _NO_COMPETITION
    return updated


@router.delete("/competitions/{competition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competition(
    competition_id: uuid.UUID, athlete: Athlete = Depends(require_athlete_access), db: AsyncSession = Depends(get_db)
) -> Response:
    if not await service.delete_competition(db, athlete.id, competition_id):
        raise _NO_COMPETITION
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- calendar feed --------------------------------------------------------------------------


async def _athlete_side(
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Athlete:
    """The feed shows the athlete's whole calendar, so only the athlete's side may open or close it."""
    if not await speaks_for_athlete(db, current_user, athlete):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the athlete can manage the calendar link")
    return athlete


@router.get("/calendar-feed", response_model=CalendarFeedStatus)
async def calendar_feed(athlete: Athlete = Depends(_athlete_side), db: AsyncSession = Depends(get_db)) -> CalendarFeedStatus:
    return await service.feed_status(db, athlete.id)


@router.post("/calendar-feed", response_model=CalendarFeedStatus)
async def make_calendar_feed(athlete: Athlete = Depends(_athlete_side), db: AsyncSession = Depends(get_db)) -> CalendarFeedStatus:
    """Makes the secret link, or replaces it (the old one stops working). The URL is only returned here."""
    return await service.enable_feed(db, athlete)


@router.delete("/calendar-feed", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar_feed(athlete: Athlete = Depends(_athlete_side), db: AsyncSession = Depends(get_db)) -> Response:
    await service.disable_feed(db, athlete.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public_router.get("/calendar/{token}.ics", include_in_schema=False)
@limiter.limit("60/minute")
async def calendar_file(request: Request, token: str, db: AsyncSession = Depends(get_db)) -> Response:
    """The feed a phone calendar subscribes to. Public: the secret in the URL is the credential."""
    text = await service.calendar_for_token(db, token)
    if text is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calendar not found")
    return Response(
        content=text,
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "private, max-age=900", "Content-Disposition": 'inline; filename="apex-cycling.ics"'},
    )

"""The squad view: every actively coached athlete's best at one event, side by
side. Times come from the records board (sqorz laps and manual results), never
from activities, so no Strava-derived number reaches a coach here. The set of
athletes is the same as the dashboard's — the ones the coach has an active link
with, which is what `require_athlete_access` grants.
"""

import uuid
from datetime import date

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus
from app.auth.models import User
from app.training.efforts import StartType
from app.training.records_service import best_entry, get_records_board
from app.training.schemas import RecordEntry


class SquadTrack(BaseModel):
    id: uuid.UUID
    name: str


class SquadRow(BaseModel):
    athlete_id: uuid.UUID
    athlete_name: str
    # Null (and no rank) for an athlete with no result at this event.
    rank: int | None
    time_ms: int | None
    gap_ms: int | None
    achieved_on: date | None
    place: str | None
    track_id: uuid.UUID | None
    source: str | None


class Squad(BaseModel):
    event_key: str
    start_type: StartType
    track_id: uuid.UUID | None
    # The tracks some athlete of the squad has a result on, for the picker.
    tracks: list[SquadTrack]
    rows: list[SquadRow]


async def build_squad(
    db: AsyncSession, coach: User, event_key: str, start_type: StartType, track_id: uuid.UUID | None
) -> Squad:
    athletes = list(
        await db.scalars(
            select(Athlete)
            .join(CoachAthlete, CoachAthlete.athlete_id == Athlete.id)
            .where(CoachAthlete.coach_user_id == coach.id, CoachAthlete.status == CoachAthleteStatus.ACTIVE)
            .order_by(Athlete.display_name)
        )
    )
    tracks: dict[uuid.UUID, str] = {}
    found: list[tuple[Athlete, RecordEntry | None]] = []
    for athlete in athletes:
        board = await get_records_board(db, athlete.id)
        for entry in board:
            if entry.track_id is not None and entry.event_key == event_key and entry.start_type == start_type:
                tracks[entry.track_id] = entry.place
        found.append((athlete, best_entry(board, event_key, start_type, track_id)))

    with_time = sorted(
        ((a, e) for a, e in found if e is not None), key=lambda pair: (pair[1].time_ms, pair[1].achieved_on, pair[0].display_name.casefold())
    )
    rows: list[SquadRow] = []
    fastest = with_time[0][1].time_ms if with_time else None
    for index, (athlete, entry) in enumerate(with_time):
        # Equal times share a rank ("1, 1, 3").
        rank = rows[-1].rank if rows and rows[-1].time_ms == entry.time_ms else index + 1
        rows.append(
            SquadRow(
                athlete_id=athlete.id,
                athlete_name=athlete.display_name,
                rank=rank,
                time_ms=entry.time_ms,
                gap_ms=entry.time_ms - fastest,
                achieved_on=entry.achieved_on,
                place=entry.place,
                track_id=entry.track_id,
                source=entry.source,
            )
        )
    rows += [
        SquadRow(
            athlete_id=athlete.id, athlete_name=athlete.display_name, rank=None, time_ms=None, gap_ms=None,
            achieved_on=None, place=None, track_id=None, source=None,
        )  # fmt: skip
        for athlete, entry in found
        if entry is None
    ]
    return Squad(
        event_key=event_key,
        start_type=start_type,
        track_id=track_id,
        tracks=[SquadTrack(id=tid, name=name) for tid, name in sorted(tracks.items(), key=lambda kv: kv[1].casefold())],
        rows=rows,
    )

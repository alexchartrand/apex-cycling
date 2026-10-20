"""The coach dashboard: one summary card per athlete the user actively
coaches — what they last did, how the last week compares with the one
before, new records, failing syncs and comments waiting for the coach.
"Form" here is recent load (sessions, laps, perceived effort), not a
fitness/fatigue model.
"""

import uuid
from datetime import date, timedelta

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus
from app.auth.models import User
from app.connections.models import IngestionRunStatus
from app.connections.service import list_ingestion_runs_for_athlete
from app.training import comments_service
from app.training.models import EventTrack, PersonalRecord, TrainingEvent, TrainingLap

WINDOW_DAYS = 7
RECORD_WINDOW_DAYS = 14


class LastSession(BaseModel):
    external_event_id: str
    name: str
    event_date: date
    lap_count: int


class WeekLoad(BaseModel):
    sessions: int
    laps: int
    # Mean perceived exertion (1–10) of the sessions that have one.
    avg_rpe: float | None


class AthleteCard(BaseModel):
    athlete_id: uuid.UUID
    athlete_name: str
    last_session: LastSession | None
    this_week: WeekLoad
    previous_week: WeekLoad
    new_records: int
    # Transponders whose most recent sync failed.
    failing_transponders: list[str]
    unread_comments: int


def _load(events: list[TrainingEvent], laps_by_event: dict[uuid.UUID, int], start: date, end: date) -> WeekLoad:
    in_window = [e for e in events if start <= e.event_date <= end]
    rpes = [e.rpe for e in in_window if e.rpe is not None]
    return WeekLoad(
        sessions=len(in_window),
        laps=sum(laps_by_event.get(e.id, 0) for e in in_window),
        avg_rpe=round(sum(rpes) / len(rpes), 1) if rpes else None,
    )


async def _lap_counts(db: AsyncSession, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not event_ids:
        return {}
    rows = await db.execute(
        select(EventTrack.training_event_id, func.count(TrainingLap.id))
        .join(TrainingLap, TrainingLap.event_track_id == EventTrack.id)
        .where(EventTrack.training_event_id.in_(event_ids), TrainingLap.excluded.is_(False))
        .group_by(EventTrack.training_event_id)
    )
    return dict(rows.all())


async def _failing_transponders(db: AsyncSession, athlete_id: uuid.UUID) -> list[str]:
    runs = await list_ingestion_runs_for_athlete(db, athlete_id=athlete_id, limit=50)
    latest: dict[str, IngestionRunStatus] = {}
    for run, code in runs:  # newest first: the first run seen per transponder is its latest
        latest.setdefault(code, run.status)
    return sorted(code for code, status in latest.items() if status == IngestionRunStatus.FAILED)


async def coach_dashboard(db: AsyncSession, coach: User, today: date | None = None) -> list[AthleteCard]:
    today = today or date.today()
    this_start = today - timedelta(days=WINDOW_DAYS - 1)
    previous_start = this_start - timedelta(days=WINDOW_DAYS)

    athletes = list(
        await db.scalars(
            select(Athlete)
            .join(CoachAthlete, CoachAthlete.athlete_id == Athlete.id)
            .where(CoachAthlete.coach_user_id == coach.id, CoachAthlete.status == CoachAthleteStatus.ACTIVE)
            .order_by(Athlete.display_name)
        )
    )
    if not athletes:
        return []
    ids = [a.id for a in athletes]

    recent_events = list(
        await db.scalars(
            select(TrainingEvent).where(TrainingEvent.athlete_id.in_(ids), TrainingEvent.event_date >= previous_start)
        )
    )
    events_by_athlete: dict[uuid.UUID, list[TrainingEvent]] = {}
    for event in recent_events:
        events_by_athlete.setdefault(event.athlete_id, []).append(event)

    last_sessions: dict[uuid.UUID, TrainingEvent] = {}
    for athlete_id in ids:
        last = await db.scalar(
            select(TrainingEvent)
            .where(TrainingEvent.athlete_id == athlete_id)
            .order_by(TrainingEvent.event_date.desc(), TrainingEvent.start_timestamp.desc().nulls_last())
            .limit(1)
        )
        if last is not None:
            last_sessions[athlete_id] = last

    laps_by_event = await _lap_counts(db, [e.id for e in recent_events] + [e.id for e in last_sessions.values()])

    new_records = dict(
        (
            await db.execute(
                select(PersonalRecord.athlete_id, func.count(PersonalRecord.id))
                .where(
                    PersonalRecord.athlete_id.in_(ids),
                    PersonalRecord.achieved_on >= today - timedelta(days=RECORD_WINDOW_DAYS - 1),
                )
                .group_by(PersonalRecord.athlete_id)
            )
        ).all()
    )

    unread: dict[uuid.UUID, int] = {}
    for item in await comments_service.inbox(db, coach):
        unread[item.athlete_id] = unread.get(item.athlete_id, 0) + item.unread_count

    cards = []
    for athlete in athletes:
        events = events_by_athlete.get(athlete.id, [])
        last = last_sessions.get(athlete.id)
        cards.append(
            AthleteCard(
                athlete_id=athlete.id,
                athlete_name=athlete.display_name,
                last_session=LastSession(
                    external_event_id=last.external_event_id,
                    name=last.title_override or last.name,
                    event_date=last.event_date,
                    lap_count=laps_by_event.get(last.id, 0),
                )
                if last
                else None,
                this_week=_load(events, laps_by_event, this_start, today),
                previous_week=_load(events, laps_by_event, previous_start, this_start - timedelta(days=1)),
                new_records=new_records.get(athlete.id, 0),
                failing_transponders=await _failing_transponders(db, athlete.id),
                unread_comments=unread.get(athlete.id, 0),
            )
        )
    return cards

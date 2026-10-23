"""The coach dashboard: one summary card per athlete the user actively
coaches — what they last did, how the last week compares with the one
before, new records, failing syncs and comments waiting for the coach, and
(v2) their fitness/fatigue/form, how much of the plan they followed, the
goal that is closest and the next race. The week comparison is recent load
(sessions, laps, perceived effort); `form` is the CTL/ATL/TSB model, which
needs power or rated sessions to say anything.

Everything is read as the coach, so an athlete's Strava activities stay out
of the load and the bests (`visible_conditions`, records from sqorz only).
"""

import uuid
from datetime import date, timedelta

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import training_load
from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus
from app.auth.models import User
from app.connections.models import IngestionRunStatus
from app.connections.service import list_ingestion_runs_for_athlete
from app.goals.models import Goal
from app.goals.service import progress_towards
from app.planning.models import PlannedSession, PlanStatus
from app.seasons import planning as race_planning
from app.seasons.models import Competition
from app.training import comments_service
from app.training.efforts import StartType
from app.training.models import EventTrack, PersonalRecord, TrainingEvent, TrainingLap
from app.training.records_service import best_entry, get_records_board

WINDOW_DAYS = 7
RECORD_WINDOW_DAYS = 14
# How far back a plan counts towards "followed the plan", and how far ahead "coming up" looks.
COMPLIANCE_DAYS = 28
UPCOMING_DAYS = 7


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


class Form(BaseModel):
    """Fitness, fatigue and form on the last day with load data."""

    ctl: float
    atl: float
    tsb: float


class PlanCompliance(BaseModel):
    """The plans of the last `COMPLIANCE_DAYS` days: done, skipped, or still
    unanswered once their day has passed (`missed`)."""

    done: int
    skipped: int
    missed: int
    # done / (done + skipped + missed); null when nothing was planned.
    compliance: float | None
    upcoming: int


class GoalProgress(BaseModel):
    goal_id: uuid.UUID
    event_key: str
    start_type: StartType
    target_time_ms: int
    target_date: date
    days_left: int
    best_ms: int | None
    progress: float | None
    achieved: bool


class NextRace(BaseModel):
    competition_id: uuid.UUID
    name: str
    competition_date: date
    priority: str
    days_until: int
    phase: str


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
    form: Form | None = None
    plan: PlanCompliance | None = None
    # The open goal with the nearest date, else the latest reached one, else the one that lapsed last.
    goal: GoalProgress | None = None
    next_race: NextRace | None = None


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


async def _form(db: AsyncSession, athlete: Athlete, coach: User, today: date) -> Form | None:
    series = (await training_load(db, athlete, coach, through=today, days=1)).days
    return Form(ctl=series[-1].ctl, atl=series[-1].atl, tsb=series[-1].tsb) if series else None


async def _plan_compliance(db: AsyncSession, athlete_id: uuid.UUID, today: date) -> PlanCompliance | None:
    plans = list(
        await db.scalars(
            select(PlannedSession).where(
                PlannedSession.athlete_id == athlete_id,
                PlannedSession.planned_date >= today - timedelta(days=COMPLIANCE_DAYS),
                PlannedSession.planned_date <= today + timedelta(days=UPCOMING_DAYS),
            )
        )
    )
    if not plans:
        return None
    past = [p for p in plans if p.planned_date < today]
    done = sum(1 for p in past if p.status == PlanStatus.DONE.value)
    skipped = sum(1 for p in past if p.status == PlanStatus.SKIPPED.value)
    missed = sum(1 for p in past if p.status == PlanStatus.PLANNED.value)
    answered = done + skipped + missed
    return PlanCompliance(
        done=done,
        skipped=skipped,
        missed=missed,
        compliance=done / answered if answered else None,
        upcoming=sum(1 for p in plans if p.planned_date >= today and p.status == PlanStatus.PLANNED.value),
    )


async def _goal_progress(db: AsyncSession, athlete_id: uuid.UUID, today: date) -> GoalProgress | None:
    goals = list(await db.scalars(select(Goal).where(Goal.athlete_id == athlete_id).order_by(Goal.target_date)))
    if not goals:
        return None
    board = await get_records_board(db, athlete_id)
    reads = []
    for goal in goals:
        best = best_entry(board, goal.event_key, goal.start_type, goal.track_id)
        reads.append(
            GoalProgress(
                goal_id=goal.id,
                event_key=goal.event_key,
                start_type=StartType(goal.start_type),
                target_time_ms=goal.target_time_ms,
                target_date=goal.target_date,
                days_left=(goal.target_date - today).days,
                best_ms=best.time_ms if best else None,
                progress=progress_towards(goal, best),
                achieved=best is not None and best.time_ms <= goal.target_time_ms,
            )
        )
    open_goals = [g for g in reads if not g.achieved and g.days_left >= 0]
    if open_goals:
        return open_goals[0]  # goals are ordered by date: the nearest one still to reach
    reached = [g for g in reads if g.achieved]
    # Nothing open: the latest goal reached, else the one that lapsed most recently (days_left < 0).
    return reached[-1] if reached else reads[-1]


async def _next_race(db: AsyncSession, athlete_id: uuid.UUID, today: date) -> NextRace | None:
    race = await db.scalar(
        select(Competition)
        .where(Competition.athlete_id == athlete_id, Competition.competition_date >= today)
        .order_by(Competition.competition_date)
        .limit(1)
    )
    if race is None:
        return None
    count = race_planning.countdown(race.competition_date, race.priority, today)
    return NextRace(
        competition_id=race.id,
        name=race.name,
        competition_date=race.competition_date,
        priority=race.priority,
        days_until=count.days_until,
        phase=count.phase,
    )


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
                form=await _form(db, athlete, coach, today),
                plan=await _plan_compliance(db, athlete.id, today),
                goal=await _goal_progress(db, athlete.id, today),
                next_race=await _next_race(db, athlete.id, today),
            )
        )
    return cards

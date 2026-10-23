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
from app.connections.models import IngestionRun, IngestionRunStatus, TransponderAssignment, DataSourceConnection
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


async def _failing_transponders(db: AsyncSession, athlete_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    """Per athlete, the transponders whose latest run failed."""
    latest = (
        select(
            IngestionRun.data_source_connection_id.label("connection_id"),
            IngestionRun.status.label("status"),
            func.row_number()
            .over(partition_by=IngestionRun.data_source_connection_id, order_by=IngestionRun.requested_at.desc())
            .label("rank"),
        )
    ).subquery()
    rows = await db.execute(
        select(TransponderAssignment.athlete_id, DataSourceConnection.external_id)
        .join(DataSourceConnection, DataSourceConnection.id == TransponderAssignment.data_source_connection_id)
        .join(latest, latest.c.connection_id == DataSourceConnection.id)
        .where(
            TransponderAssignment.athlete_id.in_(athlete_ids),
            latest.c.rank == 1,
            latest.c.status == IngestionRunStatus.FAILED,
        )
        .distinct()
    )
    failing: dict[uuid.UUID, list[str]] = {}
    for athlete_id, code in rows:
        failing.setdefault(athlete_id, []).append(code)
    return {athlete_id: sorted(codes) for athlete_id, codes in failing.items()}


async def _form(db: AsyncSession, athlete: Athlete, coach: User, today: date) -> Form | None:
    series = (await training_load(db, athlete, coach, through=today, days=1)).days
    return Form(ctl=series[-1].ctl, atl=series[-1].atl, tsb=series[-1].tsb) if series else None


async def _plan_compliance(
    db: AsyncSession, athlete_ids: list[uuid.UUID], today: date
) -> dict[uuid.UUID, PlanCompliance]:
    plans_by_athlete: dict[uuid.UUID, list[PlannedSession]] = {}
    for plan in await db.scalars(
        select(PlannedSession).where(
            PlannedSession.athlete_id.in_(athlete_ids),
            PlannedSession.planned_date >= today - timedelta(days=COMPLIANCE_DAYS),
            PlannedSession.planned_date <= today + timedelta(days=UPCOMING_DAYS),
        )
    ):
        plans_by_athlete.setdefault(plan.athlete_id, []).append(plan)

    result = {}
    for athlete_id, plans in plans_by_athlete.items():
        past = [p for p in plans if p.planned_date < today]
        done = sum(1 for p in past if p.status == PlanStatus.DONE.value)
        skipped = sum(1 for p in past if p.status == PlanStatus.SKIPPED.value)
        missed = sum(1 for p in past if p.status == PlanStatus.PLANNED.value)
        answered = done + skipped + missed
        result[athlete_id] = PlanCompliance(
            done=done,
            skipped=skipped,
            missed=missed,
            compliance=done / answered if answered else None,
            upcoming=sum(1 for p in plans if p.planned_date >= today and p.status == PlanStatus.PLANNED.value),
        )
    return result


async def _goal_progress(db: AsyncSession, athlete_ids: list[uuid.UUID], today: date) -> dict[uuid.UUID, GoalProgress]:
    goals_by_athlete: dict[uuid.UUID, list[Goal]] = {}
    for goal in await db.scalars(select(Goal).where(Goal.athlete_id.in_(athlete_ids)).order_by(Goal.target_date)):
        goals_by_athlete.setdefault(goal.athlete_id, []).append(goal)

    result = {}
    for athlete_id, goals in goals_by_athlete.items():
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
            result[athlete_id] = open_goals[0]  # goals are ordered by date: the nearest one still to reach
            continue
        reached = [g for g in reads if g.achieved]
        # Nothing open: the latest goal reached, else the one that lapsed most recently (days_left < 0).
        result[athlete_id] = reached[-1] if reached else reads[-1]
    return result


async def _next_race(db: AsyncSession, athlete_ids: list[uuid.UUID], today: date) -> dict[uuid.UUID, NextRace]:
    races: dict[uuid.UUID, Competition] = {}
    for race in await db.scalars(
        select(Competition)
        .where(Competition.athlete_id.in_(athlete_ids), Competition.competition_date >= today)
        .order_by(Competition.competition_date)
    ):
        races.setdefault(race.athlete_id, race)  # ordered by date: the first per athlete is the next one
    result = {}
    for athlete_id, race in races.items():
        count = race_planning.countdown(race.competition_date, race.priority, today)
        result[athlete_id] = NextRace(
            competition_id=race.id,
            name=race.name,
            competition_date=race.competition_date,
            priority=race.priority,
            days_until=count.days_until,
            phase=count.phase,
        )
    return result


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

    ranked = (
        select(
            TrainingEvent.id.label("id"),
            func.row_number()
            .over(
                partition_by=TrainingEvent.athlete_id,
                order_by=(TrainingEvent.event_date.desc(), TrainingEvent.start_timestamp.desc().nulls_last()),
            )
            .label("rank"),
        )
        .where(TrainingEvent.athlete_id.in_(ids))
        .subquery()
    )
    last_sessions = {
        event.athlete_id: event
        for event in await db.scalars(
            select(TrainingEvent).join(ranked, ranked.c.id == TrainingEvent.id).where(ranked.c.rank == 1)
        )
    }

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

    failing = await _failing_transponders(db, ids)
    plans = await _plan_compliance(db, ids, today)
    goals = await _goal_progress(db, ids, today)
    races = await _next_race(db, ids, today)

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
                failing_transponders=failing.get(athlete.id, []),
                unread_comments=unread.get(athlete.id, 0),
                form=await _form(db, athlete, coach, today),
                plan=plans.get(athlete.id),
                goal=goals.get(athlete.id),
                next_race=races.get(athlete.id),
            )
        )
    return cards

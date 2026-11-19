"""How far a training plan has got, from its planned sessions.

`summarize` is pure: counts (done, skipped, missed, upcoming, compliance) and
per Monday week the planned time and TSS (the workout's estimate with the FTP
on the planned date) against the done sessions' actual time and load — the
linked recording's (power TSS, else RPE), else the linked sqorz session's
(RPE). `session_facts` reads those for a set of sessions; the recording goes
through `visible_conditions`, so a coach never gets a Strava ride's numbers.
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import _ftp_on, _metric_rows, _session_seconds, visible_conditions
from app.activities.models import Activity
from app.analysis import metrics
from app.athletes.models import Athlete
from app.auth.models import User
from app.planning.models import PlannedSession, PlanStatus
from app.training.models import TrainingEvent
from app.training_plans.schemas import PlanProgress, ProgressWeek
from app.workouts import structure
from app.workouts.schemas import WorkoutItem

_ITEMS = TypeAdapter(list[WorkoutItem])


@dataclass(frozen=True)
class SessionFacts:
    day: date
    status: str
    planned_s: float | None = None
    planned_tss: float | None = None
    # Only for a done session with something linked that measured it.
    done_s: float | None = None
    done_tss: float | None = None


def _week(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _total(values: list[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return round(sum(known), 1) if known else None


def summarize(sessions: list[SessionFacts], today: date) -> PlanProgress:
    past = [s for s in sessions if s.day < today]
    done = sum(1 for s in past if s.status == PlanStatus.DONE.value)
    skipped = sum(1 for s in past if s.status == PlanStatus.SKIPPED.value)
    missed = sum(1 for s in past if s.status == PlanStatus.PLANNED.value)
    # A session done ahead of its day counts too.
    done += sum(1 for s in sessions if s.day >= today and s.status == PlanStatus.DONE.value)
    answered = done + skipped + missed
    by_week: dict[date, list[SessionFacts]] = {}
    for session in sessions:
        by_week.setdefault(_week(session.day), []).append(session)
    weeks = []
    for week, rows in sorted(by_week.items()):
        counted = [r for r in rows if r.status != PlanStatus.SKIPPED.value]
        finished = [r for r in rows if r.status == PlanStatus.DONE.value]
        weeks.append(
            ProgressWeek(
                week_start=week,
                sessions=len(counted),
                done_sessions=len(finished),
                planned_s=sum(r.planned_s or 0 for r in counted),
                planned_tss=_total([r.planned_tss for r in counted]),
                done_s=sum(r.done_s or 0 for r in finished),
                done_tss=_total([r.done_tss for r in finished]),
            )
        )
    return PlanProgress(
        done=done,
        skipped=skipped,
        missed=missed,
        upcoming=sum(1 for s in sessions if s.day >= today and s.status == PlanStatus.PLANNED.value),
        compliance=round(done / answered, 3) if answered else None,
        weeks=weeks,
    )


async def session_facts(
    db: AsyncSession, athlete: Athlete, viewer: User, sessions: list[PlannedSession]
) -> dict[uuid.UUID, SessionFacts]:
    """Facts per planned session id."""
    if not sessions:
        return {}
    rows = await _metric_rows(db, athlete.id)
    activity_ids = {s.activity_id for s in sessions if s.activity_id and s.status == PlanStatus.DONE.value}
    event_ids = {s.training_event_id for s in sessions if s.training_event_id and s.status == PlanStatus.DONE.value}
    activities = {
        a.id: a
        for a in (
            await db.scalars(select(Activity).where(*visible_conditions(athlete, viewer), Activity.id.in_(activity_ids)))
            if activity_ids
            else []
        )
    }
    events = {
        e.id: e
        for e in (await db.scalars(select(TrainingEvent).where(TrainingEvent.id.in_(event_ids))) if event_ids else [])
    }
    # A sqorz session's own recording, when only the session is linked to the plan.
    recorded = {
        a.training_event_id: a
        for a in (
            await db.scalars(
                select(Activity).where(*visible_conditions(athlete, viewer), Activity.training_event_id.in_(event_ids))
            )
            if event_ids
            else []
        )
    }
    facts = {}
    for session in sessions:
        planned_s = planned_tss = None
        if session.workout:
            estimate = structure.estimate(
                _ITEMS.validate_python(session.workout), ftp_w=_ftp_on(rows, session.planned_date)
            )
            planned_s, planned_tss = estimate.duration_s, estimate.tss
        done_s = done_tss = None
        if session.status == PlanStatus.DONE.value:
            activity = activities.get(session.activity_id) if session.activity_id else None
            if activity is None and session.training_event_id:
                activity = recorded.get(session.training_event_id)
            if activity is not None:
                done_s = activity.moving_s or activity.elapsed_s
                if activity.tss is not None:
                    done_tss = activity.tss
                elif activity.rpe is not None:
                    done_tss = metrics.srpe_training_stress(activity.rpe, done_s)
            elif (event := events.get(session.training_event_id)) is not None:
                done_s = _session_seconds(event)
                if done_s is not None and event.rpe is not None:
                    done_tss = metrics.srpe_training_stress(event.rpe, done_s)
        facts[session.id] = SessionFacts(
            day=session.planned_date,
            status=session.status,
            planned_s=planned_s,
            planned_tss=planned_tss,
            done_s=done_s,
            done_tss=done_tss,
        )
    return facts

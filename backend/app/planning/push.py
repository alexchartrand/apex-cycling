"""Marks plans whose Intervals.icu copy needs the worker's attention. The
worker (`ingestion/intervals/push_service.py`) decides what to do from the
plan as it then is: create or update the event, or delete it when the plan
is gone, skipped, has no workout or the athlete stopped the push. Nothing
here talks to Intervals.icu, and nothing commits.
"""

import uuid
from datetime import date
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.models import DataSourceConnection, DataSourceConnectionStatus, DataSourceProvider
from app.db.base import utcnow
from app.planning.models import IntervalsPlanEvent, PlannedSession, PlanStatus

PushState = Literal["pending", "sent", "failed"]


async def push_enabled(db: AsyncSession, athlete_id: uuid.UUID) -> bool:
    return (
        await db.scalar(
            select(DataSourceConnection.id).where(
                DataSourceConnection.provider == DataSourceProvider.INTERVALS_ICU,
                DataSourceConnection.athlete_id == athlete_id,
                DataSourceConnection.status == DataSourceConnectionStatus.ACTIVE,
                DataSourceConnection.push_plans.is_(True),
            )
        )
        is not None
    )


def _due(row: IntervalsPlanEvent) -> None:
    row.due_at = utcnow()
    row.attempts = 0


async def plan_changed(db: AsyncSession, plan: PlannedSession) -> None:
    """After a plan is created, edited or deleted (call it before the delete)."""
    await db.flush()  # a new plan gets its id
    row = await db.scalar(select(IntervalsPlanEvent).where(IntervalsPlanEvent.plan_id == plan.id))
    if row is None:
        if not plan.workout or not await push_enabled(db, plan.athlete_id):
            return
        row = IntervalsPlanEvent(athlete_id=plan.athlete_id, plan_id=plan.id)
        db.add(row)
    _due(row)


async def push_switched(db: AsyncSession, athlete_id: uuid.UUID, today: date) -> None:
    """After the athlete turned the push on or off: plans from today on are
    brought in line (pushed, or their events deleted). Past plans are left
    alone; turning it off also forgets the events of past ones, which stay
    on the calendar."""
    enabled = await push_enabled(db, athlete_id)
    rows = {
        row.plan_id: row
        for row in await db.scalars(select(IntervalsPlanEvent).where(IntervalsPlanEvent.athlete_id == athlete_id))
    }
    plans = await db.scalars(
        select(PlannedSession).where(PlannedSession.athlete_id == athlete_id, PlannedSession.planned_date >= today)
    )
    upcoming = set()
    for plan in plans:
        upcoming.add(plan.id)
        row = rows.get(plan.id)
        if row is None:
            if not (enabled and plan.workout and plan.status != PlanStatus.SKIPPED.value):
                continue
            row = IntervalsPlanEvent(athlete_id=athlete_id, plan_id=plan.id)
            db.add(row)
        _due(row)
    if not enabled:
        # Rows of deleted plans stay: their events still have to go.
        past = await db.scalars(select(PlannedSession.id).where(PlannedSession.id.in_(set(rows) - upcoming)))
        for plan_id in past:
            await db.delete(rows[plan_id])


async def forget_athlete(db: AsyncSession, athlete_id: uuid.UUID) -> None:
    """The connection is gone: the events stay on Intervals.icu, untracked."""
    await db.execute(delete(IntervalsPlanEvent).where(IntervalsPlanEvent.athlete_id == athlete_id))


async def push_states(db: AsyncSession, plan_ids: set[uuid.UUID]) -> dict[uuid.UUID, PushState]:
    """Where each plan's Intervals.icu copy stands, for those that have one."""
    if not plan_ids:
        return {}
    rows = await db.scalars(select(IntervalsPlanEvent).where(IntervalsPlanEvent.plan_id.in_(plan_ids)))
    states: dict[uuid.UUID, PushState] = {}
    for row in rows:
        if row.last_error is not None:
            states[row.plan_id] = "failed"
        elif row.due_at is not None:
            states[row.plan_id] = "pending"
        elif row.remote_event_id is not None:
            states[row.plan_id] = "sent"
    return states

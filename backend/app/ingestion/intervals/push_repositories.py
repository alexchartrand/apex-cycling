"""SQLAlchemy-backed plan push outbox (`planning.models.IntervalsPlanEvent`)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.models import User
from app.connections.models import DataSourceConnection, DataSourceConnectionStatus, DataSourceProvider
from app.ingestion.intervals.dtos import PlanContent, PlanPushJob
from app.planning.models import IntervalsPlanEvent, PlannedSession


class SqlAlchemyPlanPushRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def due(self, now: datetime, limit: int) -> list[PlanPushJob]:
        rows = (
            await self._db.execute(
                select(IntervalsPlanEvent, DataSourceConnection, User.locale)
                .join(
                    DataSourceConnection,
                    (DataSourceConnection.athlete_id == IntervalsPlanEvent.athlete_id)
                    & (DataSourceConnection.provider == DataSourceProvider.INTERVALS_ICU)
                    & (DataSourceConnection.status == DataSourceConnectionStatus.ACTIVE),
                )
                .join(Athlete, Athlete.id == IntervalsPlanEvent.athlete_id)
                .outerjoin(User, User.id == Athlete.user_id)
                .where(IntervalsPlanEvent.due_at.is_not(None), IntervalsPlanEvent.due_at <= now)
                .order_by(IntervalsPlanEvent.due_at)
                .limit(limit)
            )
        ).all()
        plan_ids = [row.plan_id for row, _, _ in rows]
        plans = {
            p.id: p for p in await self._db.scalars(select(PlannedSession).where(PlannedSession.id.in_(plan_ids)))
        }
        jobs = []
        for row, connection, locale in rows:
            api_key = (connection.credentials or {}).get("api_key")
            if not api_key:
                continue
            plan = plans.get(row.plan_id)
            jobs.append(
                PlanPushJob(
                    id=row.id,
                    connection_id=connection.id,
                    api_key=api_key,
                    push_enabled=connection.push_plans,
                    plan_id=row.plan_id,
                    plan=PlanContent(
                        id=plan.id,
                        title=plan.title,
                        planned_date=plan.planned_date,
                        description=plan.description,
                        workout=plan.workout,
                        status=plan.status,
                    )
                    if plan is not None
                    else None,
                    remote_event_id=row.remote_event_id,
                    payload_hash=row.payload_hash,
                    attempts=row.attempts,
                    locale=locale,
                )
            )
        return jobs

    async def mark_sent(self, job_id: uuid.UUID, event_id: str, payload_hash: str) -> None:
        row = await self._db.get(IntervalsPlanEvent, job_id)
        row.remote_event_id, row.payload_hash = event_id, payload_hash
        row.due_at, row.attempts, row.last_error = None, 0, None

    async def forget(self, job_id: uuid.UUID) -> None:
        row = await self._db.get(IntervalsPlanEvent, job_id)
        if row is not None:
            await self._db.delete(row)

    async def mark_failed(self, job_id: uuid.UUID, error: str, retry_at: datetime | None) -> None:
        row = await self._db.get(IntervalsPlanEvent, job_id)
        row.attempts += 1
        row.last_error, row.due_at = error[:500], retry_at

    async def postpone(self, job_id: uuid.UUID, until: datetime) -> None:
        row = await self._db.get(IntervalsPlanEvent, job_id)
        row.due_at = until

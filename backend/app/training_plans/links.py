"""Loosening a plan's ties when what it points at goes (kept apart from
`service.py` so goals and seasons can import it without a cycle)."""

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.training_plans.models import TrainingPlan


async def detach_goal(db: AsyncSession, goal_id: uuid.UUID) -> None:
    await db.execute(update(TrainingPlan).where(TrainingPlan.goal_id == goal_id).values(goal_id=None))


async def detach_competition(db: AsyncSession, competition_id: uuid.UUID) -> None:
    await db.execute(
        update(TrainingPlan).where(TrainingPlan.competition_id == competition_id).values(competition_id=None)
    )

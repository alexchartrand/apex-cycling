import uuid
from datetime import date

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, String, Text, Uuid, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TrainingPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A block of training towards one goal, for one sport (`kinds.PLAN_SPORTS`),
    written by the athlete, their coach or the AI coach. An athlete may run
    several at once (a track plan and a road plan). Its planned sessions point
    at it (`PlannedSession.training_plan_id`); progress is derived from them on
    every read (`progress.py`), nothing is stored.

    `phases` is the broad shape (`schemas.Phase`: base, build, peak, taper…),
    `weeks` the week-by-week outline of what isn't detailed session by session
    yet (`schemas.OutlineWeek`, what the AI coach refines in its reports).
    `goal_id` (a time to beat, track plans only) and `competition_id` (the race)
    are nulled when those are deleted.
    """

    __tablename__ = "training_plans"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    sport: Mapped[str] = mapped_column(String(32))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    goal_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("goals.id"), nullable=True)
    competition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("competitions.id"), nullable=True)
    hours_per_week: Mapped[float | None] = mapped_column(Float, nullable=True)
    phases: Mapped[list[dict]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    weeks: Mapped[list[dict]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    # Null once the author's account is gone, and for a plan the AI wrote.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_ai: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # The proposal it was accepted from (no FK: the proposal may be gone).
    ai_proposal_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

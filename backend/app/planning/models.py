import enum
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlanStatus(str, enum.Enum):
    PLANNED = "planned"
    DONE = "done"
    SKIPPED = "skipped"


class PlannedSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A session someone (usually the coach) put on an athlete's calendar.
    `targets` is the list of planned efforts (`planning/schemas.py::PlannedEffort`),
    the older free-form plan; `workout` is a copy of a workout's step tree
    (`workouts/schemas.py::WorkoutItem`), taken when it was scheduled so later
    edits to the library workout (`source_workout_id`, no FK since presets
    aren't rows) never rewrite the plan.
    The athlete marks it done or skipped, or links it to the sqorz session
    that was actually ridden (`training_event_id`, which makes it done).
    """

    __tablename__ = "planned_sessions"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    # Null once the author's account is gone.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    planned_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    targets: Mapped[list[dict]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    workout: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    source_workout_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default=PlanStatus.PLANNED.value)
    training_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("training_events.id"), nullable=True)


class IntervalsPlanEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A plan's copy on the athlete's Intervals.icu calendar, and the outbox
    that keeps it in step: a change to the plan sets `due_at`, and the worker
    (`ingestion/intervals/push_service.py`) creates, updates or deletes the
    event, then clears it — or retries later, `attempts` and `last_error`
    saying why. `plan_id` has no FK because the row outlives a deleted plan
    until its event is deleted too. `remote_event_id` is the event we
    created (null until it exists); `payload_hash` what it last received.
    """

    __tablename__ = "intervals_plan_events"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
    remote_event_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

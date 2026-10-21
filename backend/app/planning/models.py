import enum
import uuid
from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlanStatus(str, enum.Enum):
    PLANNED = "planned"
    DONE = "done"
    SKIPPED = "skipped"


class PlannedSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A session someone (usually the coach) put on an athlete's calendar.
    `targets` is the list of planned efforts (`planning/schemas.py::PlannedEffort`).
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
    status: Mapped[str] = mapped_column(String(16), default=PlanStatus.PLANNED.value)
    training_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("training_events.id"), nullable=True)

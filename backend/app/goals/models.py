import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Goal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A time to beat: an event (`STANDARD_EVENTS` key and start type), on a
    given track or anywhere, by a date. Only the target is stored. The current
    best, the gap, whether it's reached and the predicted time are worked out
    on every read (`goals/service.py`), so they follow lap edits and new
    results. `baseline_ms` is the best at the moment the goal was set (null if
    there was none), the starting point of the progress bar.
    """

    __tablename__ = "goals"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(16))
    start_type: Mapped[str] = mapped_column(String(16))
    track_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tracks.id"), nullable=True)
    target_time_ms: Mapped[int] = mapped_column(Integer)
    target_date: Mapped[date] = mapped_column(Date)
    baseline_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

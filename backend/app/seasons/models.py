import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Season(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The start of a season. A season lasts until the day before the next
    one starts (the latest has no end), so only start dates are stored and
    the bests of a season are worked out on every read (`seasons/service.py`)."""

    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("athlete_id", "start_date", name="uq_season_athlete_start"),)

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[date] = mapped_column(Date)


class Competition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A race on the athlete's calendar. `priority` A/B/C sets how long the
    taper before it is (`seasons/planning.py`); `goal_id` ties it to the goal
    the athlete is aiming to reach there."""

    __tablename__ = "competitions"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    competition_date: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(120))
    priority: Mapped[str] = mapped_column(String(1), default="B")
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("goals.id"), nullable=True)


class CalendarFeed(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The secret link that lets a phone calendar subscribe to an athlete's
    plans and races. Only the hash of the token is stored (shown once, like an
    invite); making a new link replaces the old one."""

    __tablename__ = "calendar_feeds"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

import uuid

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AeroTest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One aero run kept for comparison: the laps of a session ridden in one
    setup (position, helmet, skinsuit, bike), and what to assume about them.

    Only the inputs are stored. The CdA is recomputed from the laps and the
    linked recording each time it's read (`aero/service.py`), so it follows lap
    edits, clock-offset changes and new weigh-ins, never shows a viewer
    numbers from a recording they may not see (Strava), and has nothing to
    clean up when a recording goes away.
    """

    __tablename__ = "aero_tests"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    training_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_events.id"), index=True)
    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracks.id"))

    label: Mapped[str] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    helmet: Mapped[str | None] = mapped_column(String(100), nullable=True)
    skinsuit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bike: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lap ids (strings) picked by hand; null = the automatic steady-lap pick.
    lap_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # `AeroInputs` overrides; null = the default (see `aero/schemas.py`).
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_hpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rider_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    bike_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    crr: Mapped[float | None] = mapped_column(Float, nullable=True)

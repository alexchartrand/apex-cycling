import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Bike(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One of the athlete's bikes. `weight_kg` (the bike alone) is what the
    aero lab assumes for a session ridden on it, instead of its 8 kg default.
    """

    __tablename__ = "bikes"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class GearSetup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A chainring, a cog and a tire (with its Crr, when known) on one bike. `rollout_mm` is the distance
    the wheel travels in one turn, measured with the rider on the bike (the
    tire's circumference is a few millimetres short). Assigned to a session
    (`TrainingEvent.gear_setup_id`) or to one effort of it
    (`TrainingLap.effort_gear_setup_id`); a fixed gear's cadence then follows
    from the lap speed (`equipment/service.py`).
    """

    __tablename__ = "gear_setups"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    bike_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bikes.id"), index=True)
    chainring_teeth: Mapped[int] = mapped_column(Integer)
    cog_teeth: Mapped[int] = mapped_column(Integer)
    rollout_mm: Mapped[float] = mapped_column(Float)
    tire: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # The tire's rolling resistance coefficient, from the standard-tire list
    # or typed in.
    crr: Mapped[float | None] = mapped_column(Float, nullable=True)

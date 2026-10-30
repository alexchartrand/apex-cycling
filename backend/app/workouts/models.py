import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A reusable workout in its owner's library. `steps` is the step tree
    (`workouts/schemas.py::WorkoutItem`); duration, TSS and the intensity
    profile are derived from it on every read (`workouts/structure.py`).
    The library is per user: an athlete's personal workouts and a coach's
    library are the same thing, and a coach's athletes can browse it.
    """

    __tablename__ = "workouts"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    steps: Mapped[list[dict]] = mapped_column(JSON, default=list, server_default=text("'[]'"))

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Athlete(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An athlete profile. Not every athlete has a login (`user_id` may be
    null for athletes a club_admin manages directly, e.g. juniors), and not
    every athlete belongs to a club (`club_id` is null for solo self-serve
    users) — see plan Context for why neither is required.
    """

    __tablename__ = "athletes"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=True, index=True
    )
    club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id"), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    birthdate: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="athlete", foreign_keys=[user_id])


class CoachAthleteStatus(str, enum.Enum):
    PENDING_ATHLETE_ACCEPTANCE = "pending_athlete_acceptance"
    PENDING_COACH_ACCEPTANCE = "pending_coach_acceptance"
    ACTIVE = "active"
    REVOKED = "revoked"


class CoachAthlete(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Links a coach to an athlete's data. For self-serve athletes this
    requires mutual consent (see plan Auth & Permissions): whichever side
    didn't initiate must accept before `status` becomes ACTIVE. For athlete
    records a club_admin manages directly (no `user_id`), the club_admin can
    activate immediately since there's no independent person to consent.
    """

    __tablename__ = "coach_athletes"
    __table_args__ = (UniqueConstraint("coach_user_id", "athlete_id", name="uq_coach_athlete"),)

    coach_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    initiated_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[CoachAthleteStatus] = mapped_column(
        Enum(
            CoachAthleteStatus,
            name="coach_athlete_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

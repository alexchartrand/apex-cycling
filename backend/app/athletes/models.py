import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.auth.models import User


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
    # "female" / "male": the competition category, which is what UCI age
    # categories and records boards split on — not a gender-identity field.
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The club whose leaderboard this athlete agreed to appear on. Opting in
    # only counts while it is still the athlete's club (`club_id`), so moving
    # to another club never carries the consent along.
    leaderboard_club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id"), nullable=True)

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
    # Null once the initiating user deleted their account.
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[CoachAthleteStatus] = mapped_column(
        Enum(
            CoachAthleteStatus,
            name="coach_athlete_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AthleteMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One dated physiology measurement. Every value is optional so a row can
    record just a weigh-in or just a new FTP; "the value at date X" is, per
    field, the latest non-null value on or before X (see
    `athletes/service.py::metrics_at`), which W/kg and TSS build on. One row
    per athlete per day — re-posting a date updates that row.
    """

    __tablename__ = "athlete_metrics"
    __table_args__ = (UniqueConstraint("athlete_id", "effective_date", name="uq_athlete_metric_date"),)

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    effective_date: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    ftp_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resting_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)

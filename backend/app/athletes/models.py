import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import ColumnElement

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
    display_name: Mapped[str] = mapped_column(String(255))
    birthdate: Mapped[date | None] = mapped_column(Date, nullable=True)
    # "female" / "male": the competition category, which is what UCI age
    # categories and records boards split on — not a gender-identity field.
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="athlete", foreign_keys=[user_id])
    # Always loaded: access checks and the API read it on every request. Change
    # it through the collection (`join_club` / `leave_club`), not by bulk SQL
    # on a loaded athlete, or the loaded copy goes stale.
    club_links: Mapped[list["AthleteClub"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="AthleteClub.joined_at, AthleteClub.club_id"
    )

    @property
    def club_ids(self) -> list[uuid.UUID]:
        """The rosters this athlete is on, earliest joined first."""
        return [link.club_id for link in self.club_links]

    @property
    def leaderboard_club_ids(self) -> list[uuid.UUID]:
        """The clubs whose leaderboard this athlete agreed to appear on."""
        return [link.club_id for link in self.club_links if link.leaderboard_opt_in]

    def join_club(self, club_id: uuid.UUID) -> None:
        if club_id not in self.club_ids:
            self.club_links.append(AthleteClub(club_id=club_id))

    def leave_club(self, club_id: uuid.UUID) -> None:
        """Takes the athlete off the roster, which also withdraws the leaderboard
        consent given there for good."""
        self.club_links = [link for link in self.club_links if link.club_id != club_id]


class AthleteClub(Base):
    """One roster entry. `leaderboard_opt_in` is the athlete's consent to
    appear on this club's leaderboard; it lives on the entry, so leaving the
    club (or the club going away) ends it and rejoining never revives it."""

    __tablename__ = "athlete_clubs"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), primary_key=True)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id"), primary_key=True, index=True)
    leaderboard_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def on_roster_of(club_ids) -> ColumnElement[bool]:
    """`Athlete` rows on the roster of any of `club_ids` (a collection or a subquery)."""
    return Athlete.id.in_(select(AthleteClub.athlete_id).where(AthleteClub.club_id.in_(club_ids)))


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

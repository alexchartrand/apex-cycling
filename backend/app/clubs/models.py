import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ClubRole(str, enum.Enum):
    ATHLETE = "athlete"
    COACH = "coach"
    CLUB_ADMIN = "club_admin"


class Club(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clubs"

    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    memberships: Mapped[list["ClubMembership"]] = relationship(back_populates="club")


class ClubMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "club_memberships"
    __table_args__ = (UniqueConstraint("user_id", "club_id", name="uq_club_membership_user_club"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id"), index=True)
    role: Mapped[ClubRole] = mapped_column(
        Enum(ClubRole, name="club_role", values_callable=lambda enum_cls: [e.value for e in enum_cls])
    )

    club: Mapped["Club"] = relationship(back_populates="memberships")

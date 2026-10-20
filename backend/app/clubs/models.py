import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
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


def _club_role_column() -> Enum:
    return Enum(ClubRole, name="club_role", values_callable=lambda enum_cls: [e.value for e in enum_cls])


class ClubInvite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A link a club admin hands out (or emails) to bring someone into the
    club in a given role. Only the SHA-256 of the token is stored. It works
    until it expires, is revoked, or has been used `max_uses` times
    (null = no limit).
    """

    __tablename__ = "club_invites"

    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[ClubRole] = mapped_column(_club_role_column())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Who the link was emailed to, when it was (informational).
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Null once the admin who created it deleted their account.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ClubSqorzAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Says a club runs (or rides at) the facility behind a sqorz account, so
    its admins may edit that account's tracks (`tracks_service.TrackEditRights`).
    Only platform admins create these. Several clubs may share one facility.
    """

    __tablename__ = "club_sqorz_accounts"
    __table_args__ = (UniqueConstraint("club_id", "sqorz_account_id", name="uq_club_sqorz_account"),)

    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id"), index=True)
    sqorz_account_id: Mapped[str] = mapped_column(String(255), index=True)

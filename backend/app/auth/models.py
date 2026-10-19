from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.athletes.models import Athlete


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # UI preferences, synced across devices. Null means "never chosen": the
    # device keeps its own choice (browser language / system theme).
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(16), nullable=True)

    athlete: Mapped["Athlete | None"] = relationship(
        back_populates="user", uselist=False, foreign_keys="Athlete.user_id"
    )

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.crypto import EncryptedJSON
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DataSourceProvider(str, enum.Enum):
    SQORZ = "sqorz"
    STRAVA = "strava"
    GARMIN = "garmin"
    INTERVALS_ICU = "intervals_icu"


class DataSourceConnectionStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class DataSourceConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tracked external data source. For `sqorz`, `external_id` is a
    transponder code and this row is NOT owned by any one athlete or club —
    see plan Context: transponders are a shared pool, attribution lives in
    `TransponderAssignment` instead. For future personal sources (Strava,
    Garmin), `athlete_id` will be set directly.
    """

    __tablename__ = "data_source_connections"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_connection_provider_external_id"),)

    provider: Mapped[DataSourceProvider] = mapped_column(
        Enum(
            DataSourceProvider,
            name="data_source_provider",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    athlete_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("athletes.id"), nullable=True, index=True)
    # Encrypted at rest (app/core/crypto.py).
    credentials: Mapped[dict | None] = mapped_column(EncryptedJSON, nullable=True)
    status: Mapped[DataSourceConnectionStatus] = mapped_column(
        Enum(
            DataSourceConnectionStatus,
            name="data_source_connection_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=DataSourceConnectionStatus.ACTIVE,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Informational only for sqorz (the facility's own account), never an FK
    # to our `clubs` table — see plan Data Model.
    sqorz_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sqorz_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    assignments: Mapped[list["TransponderAssignment"]] = relationship(back_populates="connection")


class TransponderAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Self-reported "I used transponder X from date A to date B" record.
    Overlapping ranges for the same connection are rejected at the
    application layer (see connections/service.py) only when they belong to
    DIFFERENT athletes, since one transponder maps to at most one athlete at
    any given time. Overlapping ranges reported by the SAME athlete are
    merged into a single row spanning the union instead.
    """

    __tablename__ = "transponder_assignments"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_source_connections.id"), index=True
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Null once the user who entered it deleted their account.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    connection: Mapped["DataSourceConnection"] = relationship(back_populates="assignments")


class IngestionRunStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class IngestionRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_runs"

    data_source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_source_connections.id"), index=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[IngestionRunStatus] = mapped_column(
        Enum(
            IngestionRunStatus,
            name="ingestion_run_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=IngestionRunStatus.PENDING,
    )
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Activities a sync run brought in (personal sources; null for sqorz).
    imported_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RawSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Full raw JSON retained for replay/audit and for M3 normalization.
    Deduped by `content_hash` so an unchanged upstream response doesn't
    create a new row every poll.
    """

    __tablename__ = "raw_snapshots"

    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_runs.id"), index=True)
    provider: Mapped[DataSourceProvider] = mapped_column(
        Enum(
            DataSourceProvider,
            name="data_source_provider",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )
    external_ref: Mapped[str] = mapped_column(String(255), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

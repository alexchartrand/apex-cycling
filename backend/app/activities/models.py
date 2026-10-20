import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import false

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ActivitySource(str, enum.Enum):
    UPLOAD = "upload"
    INTERVALS_ICU = "intervals_icu"
    STRAVA = "strava"


class Activity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One ride/workout recorded outside sqorz (head unit, watch, power meter),
    owned by an athlete. The per-second data lives in `ActivityStream`.

    `source` also decides who may see it: Strava's API terms only allow a
    user's Strava data to be shown to that user, so Strava activities are
    owner-only (coaches and club admins are filtered out, see T7.6).
    """

    __tablename__ = "activities"
    __table_args__ = (
        # The same file twice, or the same upstream activity synced twice.
        UniqueConstraint("athlete_id", "file_sha256", name="uq_activity_athlete_file"),
        UniqueConstraint("athlete_id", "source", "external_id", name="uq_activity_athlete_source_external"),
    )

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    source: Mapped[ActivitySource] = mapped_column(
        Enum(ActivitySource, name="activity_source", values_callable=lambda enum_cls: [e.value for e in enum_cls])
    )
    # The upstream id for synced sources; null for uploads.
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_source_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_source_connections.id"), nullable=True, index=True
    )

    # The sqorz session this ride contains (the same track laps), if any.
    # `clock_offset_s` is added to the device's timestamps to get sqorz time
    # (the device's clock runs that many seconds behind). `session_link_manual`
    # means the athlete chose the link or its absence, so auto-linking leaves
    # it alone.
    training_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("training_events.id"), nullable=True, index=True
    )
    clock_offset_s: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    session_link_manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sport: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    elapsed_s: Mapped[float] = mapped_column(Float)
    # Time actually moving; equals elapsed_s when the file carries no pauses.
    moving_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    has_power: Mapped[bool] = mapped_column(Boolean, default=False)
    has_heart_rate: Mapped[bool] = mapped_column(Boolean, default=False)
    has_cadence: Mapped[bool] = mapped_column(Boolean, default=False)

    # Summaries, filled when the activity is parsed (avg_*, max_*) and by the
    # metrics engine (normalized power, TSS).
    avg_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Power-based training stress: needs the rider's FTP on that day, so it is
    # refreshed whenever their FTP history changes (metrics_service.refresh_tss).
    tss: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_heart_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_heart_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cadence: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)

    # The athlete's own notes. RPE (1-10) stands in for power when there is none:
    # the training load falls back to duration x effort (analysis/metrics.py).
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rpe: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The original upload, relative to UPLOADS_DIR (app/activities/storage.py).
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ActivityStream(Base):
    """Per-sample channels of one activity, each a zlib-compressed float array
    (app/activities/streams.py). A channel the file doesn't carry is null."""

    __tablename__ = "activity_streams"

    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id"), primary_key=True)
    sample_count: Mapped[int] = mapped_column(Integer)
    time_s: Mapped[bytes] = mapped_column(LargeBinary)
    power_w: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    heart_rate: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    cadence: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    speed_mps: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    distance_m: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    altitude_m: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)


class ActivityPowerCurve(Base):
    """Mean-maximal power: the best average power the activity holds over
    `duration_s` seconds, at the standard durations the metrics engine uses."""

    __tablename__ = "activity_power_curves"

    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id"), primary_key=True)
    duration_s: Mapped[int] = mapped_column(Integer, primary_key=True)
    power_w: Mapped[float] = mapped_column(Float)

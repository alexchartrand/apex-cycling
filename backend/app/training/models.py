import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Track(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A stable track/circuit dimension, upserted by external id. Scoped by
    sqorz's own `account_id` (facility), not by any track-trainer `club_id`
    — see plan Data Model: a session can include athletes from many
    different (or no) track-trainer clubs.
    """

    __tablename__ = "tracks"
    __table_args__ = (UniqueConstraint("sqorz_account_id", "external_track_id", name="uq_track_account_external_id"),)

    sqorz_account_id: Mapped[str] = mapped_column(String(255), index=True)
    external_track_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    track_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_method: Mapped[str | None] = mapped_column(String(64), nullable=True)

    loops: Mapped[list["TrackLoop"]] = relationship(back_populates="track")
    views: Mapped[list["TrackView"]] = relationship(back_populates="track")


class TrackLoop(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A checkpoint on a track, upserted by external id. `distance_m` (the
    cumulative distance from the track's start line) is only sometimes
    reported by sqorz — kept nullable, and never clobbered with a null on a
    later upsert once a real value has been seen (see normalizer.py). Loop
    order genuinely varies session to session (extra/disabled checkpoints),
    so there is deliberately no stable "position" here — see
    `LapSegmentTime.sequence_index` for the per-lap order instead.
    """

    __tablename__ = "track_loops"
    __table_args__ = (UniqueConstraint("track_id", "external_loop_id", name="uq_track_loop_external_id"),)

    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracks.id"), index=True)
    external_loop_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    track: Mapped["Track"] = relationship(back_populates="loops")


class TrackView(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named grouping of loops (e.g. "200m" flying-lap splits), stable
    across sessions for the same track and upserted by external id.
    """

    __tablename__ = "track_views"
    __table_args__ = (UniqueConstraint("track_id", "external_track_view_id", name="uq_track_view_external_id"),)

    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracks.id"), index=True)
    external_track_view_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    circuit: Mapped[bool] = mapped_column(Boolean, default=False)

    track: Mapped["Track"] = relationship(back_populates="views")
    view_loops: Mapped[list["TrackViewLoop"]] = relationship(
        back_populates="track_view", order_by="TrackViewLoop.sequence_index"
    )


class TrackViewLoop(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One loop in a track view's ordered sequence. A loop may repeat within
    one view (e.g. a circuit view passing the same checkpoint twice), so
    uniqueness is on position, not on the loop itself.
    """

    __tablename__ = "track_view_loops"
    __table_args__ = (UniqueConstraint("track_view_id", "sequence_index", name="uq_track_view_loop_sequence"),)

    track_view_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("track_views.id"), index=True)
    track_loop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("track_loops.id"), index=True)
    sequence_index: Mapped[int] = mapped_column(Integer)

    track_view: Mapped["TrackView"] = relationship(back_populates="view_loops")
    track_loop: Mapped["TrackLoop"] = relationship()


class TrainingEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One athlete's private copy of a sqorz training session/day, upserted
    by external id. Owned by `athlete_id` — two athletes who both appear in
    the same physical sqorz event (e.g. two transponders at the same
    session) each get their own independent `TrainingEvent` row (and
    everything under it: `EventClass`, `EventTrack`, `TrainingLap`,
    `LapSegmentTime`), since this data is meant to be manually editable per
    athlete without affecting anyone else's copy. Contrast with `Track` /
    `TrackLoop` / `TrackView`, which stay a shared dimension since they just
    describe the physical facility, not recorded results.
    """

    __tablename__ = "training_events"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id", "sqorz_account_id", "external_event_id", name="uq_event_athlete_account_external_id"
        ),
    )

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    sqorz_account_id: Mapped[str] = mapped_column(String(255), index=True)
    external_event_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    sport_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    classes: Mapped[list["EventClass"]] = relationship(back_populates="training_event")
    event_tracks: Mapped[list["EventTrack"]] = relationship(back_populates="training_event")


class EventClass(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_classes"
    __table_args__ = (UniqueConstraint("training_event_id", "class_code", name="uq_event_class_code"),)

    training_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_events.id"), index=True)
    class_code: Mapped[str] = mapped_column(String(64))
    class_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    class_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    training_event: Mapped["TrainingEvent"] = relationship(back_populates="classes")


class EventTrack(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-event snapshot of a track's config. `enabled`/`gate`/`start_from`
    can vary run to run even though the `Track` itself is a stable
    dimension (see plan Data Model).
    """

    __tablename__ = "event_tracks"
    __table_args__ = (UniqueConstraint("training_event_id", "track_id", name="uq_event_track"),)

    training_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_events.id"), index=True)
    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracks.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    gate: Mapped[bool] = mapped_column(Boolean, default=False)
    start_from: Mapped[str | None] = mapped_column(String(64), nullable=True)

    training_event: Mapped["TrainingEvent"] = relationship(back_populates="event_tracks")
    track: Mapped["Track"] = relationship()
    laps: Mapped[list["TrainingLap"]] = relationship(back_populates="event_track")


class TrainingLap(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One recorded lap for one transponder, owned by the same `athlete_id`
    as its parent `TrainingEvent` (see normalizer.py: the owning athlete is
    resolved once per `trainingDetail` from the `TransponderAssignment`
    window covering `eventDate`, and trainingDetail entries with no covering
    assignment are dropped entirely at ingestion — so every lap that reaches
    this table always has a resolved owner).
    """

    __tablename__ = "training_laps"
    __table_args__ = (UniqueConstraint("event_track_id", "external_lap_id", name="uq_training_lap_external_id"),)

    event_track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_tracks.id"), index=True)
    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    transponder_code: Mapped[str] = mapped_column(String(255), index=True)
    class_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_lap_id: Mapped[str] = mapped_column(String(255), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    from_start: Mapped[bool] = mapped_column(Boolean, default=True)
    start_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    event_track: Mapped["EventTrack"] = relationship(back_populates="laps")
    segment_times: Mapped[list["LapSegmentTime"]] = relationship(
        back_populates="training_lap", order_by="LapSegmentTime.sequence_index"
    )


class LapSegmentTime(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The fact table progression charts read. `time_ms` null means the
    checkpoint was missed — excluded (not zero-filled) from whole-lap and
    view sums so an incomplete lap isn't silently under-reported.
    """

    __tablename__ = "lap_segment_times"
    __table_args__ = (UniqueConstraint("training_lap_id", "sequence_index", name="uq_lap_segment_sequence"),)

    training_lap_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_laps.id"), index=True)
    track_loop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("track_loops.id"), index=True)
    sequence_index: Mapped[int] = mapped_column(Integer)
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    training_lap: Mapped["TrainingLap"] = relationship(back_populates="segment_times")
    track_loop: Mapped["TrackLoop"] = relationship()

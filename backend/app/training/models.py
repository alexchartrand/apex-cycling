import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, false, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Track(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A stable track/circuit dimension, upserted by external id. Scoped by
    sqorz's own `account_id` (facility), not by any apex-cycling `club_id`
    — see plan Data Model: a session can include athletes from many
    different (or no) apex-cycling clubs.
    """

    __tablename__ = "tracks"
    __table_args__ = (UniqueConstraint("sqorz_account_id", "external_track_id", name="uq_track_account_external_id"),)

    sqorz_account_id: Mapped[str] = mapped_column(String(255), index=True)
    external_track_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    track_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Sqorz never reports a track's total circuit length (only sparse
    # per-checkpoint cumulative distance — see TrackLoop), so this has no
    # ingestion path; it's a manually-set fact about the physical facility,
    # used to place sensors proportionally on the track schema diagram.
    length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # More manually-set facts about the facility (see `tracks_service`); sync
    # never writes them. Null = not known.
    indoor: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)

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
    # Not drawn on the track diagram (an extra checkpoint that isn't part of
    # the reference layout). Display only — timings still use the loop.
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

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
    # Left out of view pickers (progression…); display only.
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

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
    # The athlete's own annotations. `name` is re-written from sqorz on every
    # sync, so a renamed session lives in `title_override` instead; sync never
    # touches any of these.
    title_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rpe: Mapped[int | None] = mapped_column(Integer, nullable=True)  # rate of perceived exertion, 1-10
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))

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
    # Edits made by the athlete; sync never overwrites them. An excluded lap
    # (bad timing, a warm-up…) stays in its effort but never counts toward
    # records or progression. `effort_label` names the effort this lap
    # *starts* — efforts are computed, not stored, so their first lap carries it.
    excluded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effort_label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    event_track: Mapped["EventTrack"] = relationship(back_populates="laps")
    segment_times: Mapped[list["LapSegmentTime"]] = relationship(
        back_populates="training_lap", order_by="LapSegmentTime.sequence_index"
    )


class LapSegmentTime(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The fact table progression charts read. `time_ms` is the raw
    cumulative elapsed time since lap start at this checkpoint — it matches
    sqorz's `lapTimes` 1:1 and is NOT a per-segment duration, so it must
    never be summed directly. Whole-lap time is simply the last segment's
    value; view times and per-segment durations are derived by boundary
    subtraction / delta conversion at read time (see `training/service.py`:
    `_whole_lap_time_ms`, `_view_time_ms`, `_segment_deltas`). `time_ms`
    null means that checkpoint's capture was missed — whether that blocks a
    given computation depends on which segment(s) it is (see those
    functions' docstrings).
    """

    __tablename__ = "lap_segment_times"
    __table_args__ = (UniqueConstraint("training_lap_id", "sequence_index", name="uq_lap_segment_sequence"),)

    training_lap_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_laps.id"), index=True)
    track_loop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("track_loops.id"), index=True)
    sequence_index: Mapped[int] = mapped_column(Integer)
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    training_lap: Mapped["TrainingLap"] = relationship(back_populates="segment_times")
    track_loop: Mapped["TrackLoop"] = relationship()


class PersonalRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An athlete's best computed result for one standard event on one
    track and start type (see `training/distances.py::STANDARD_EVENTS`).
    Derived data: `records_service.recompute_personal_records` rebuilds an
    athlete's rows from their laps after every sqorz normalization and every
    lap edit, so never edit these directly. `event_key` / `start_type` are
    plain strings ("500m", "standing") rather than DB enums.
    """

    __tablename__ = "personal_records"
    __table_args__ = (
        UniqueConstraint("athlete_id", "track_id", "event_key", "start_type", name="uq_personal_record_key"),
    )

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracks.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(16))
    start_type: Mapped[str] = mapped_column(String(16))
    time_ms: Mapped[int] = mapped_column(Integer)
    achieved_on: Mapped[date] = mapped_column(Date)
    training_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_events.id"), index=True)
    # First lap of the record performance (a 4 km pursuit spans many).
    training_lap_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_laps.id"), index=True)


class ManualResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A result the athlete entered by hand — a race, or a track with no
    sqorz timing. Counts toward the records board alongside computed
    records. Either `track_id` (a known track) or free-text `venue`.
    """

    __tablename__ = "manual_results"

    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id"), index=True)
    track_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tracks.id"), nullable=True, index=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_key: Mapped[str] = mapped_column(String(16))
    start_type: Mapped[str] = mapped_column(String(16))
    time_ms: Mapped[int] = mapped_column(Integer)
    achieved_on: Mapped[date] = mapped_column(Date)
    is_competition: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class SessionComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One message in the thread on an athlete's session, between the athlete
    and the people with access to their data (coaches, club admins). Hangs off
    the athlete's private `TrainingEvent`, so it goes with it; sync never
    touches it. Comments an account wrote are deleted with the account.
    """

    __tablename__ = "session_comments"

    training_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_events.id"), index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionCommentRead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Where a user has read up to in one session's thread: comments by
    others newer than `last_read_at` are "new" in their inbox."""

    __tablename__ = "session_comment_reads"
    __table_args__ = (UniqueConstraint("user_id", "training_event_id", name="uq_session_comment_read"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    training_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_events.id"), index=True)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

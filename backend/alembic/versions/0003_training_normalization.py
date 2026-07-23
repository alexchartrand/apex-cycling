"""training normalization: tracks, track_loops, track_views, track_view_loops,
training_events, event_classes, event_tracks, training_laps, lap_segment_times

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sqorz_account_id", sa.String(length=255), nullable=False),
        sa.Column("external_track_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("track_type", sa.String(length=64), nullable=True),
        sa.Column("validation_method", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("sqorz_account_id", "external_track_id", name="uq_track_account_external_id"),
    )
    op.create_index("ix_tracks_sqorz_account_id", "tracks", ["sqorz_account_id"])
    op.create_index("ix_tracks_external_track_id", "tracks", ["external_track_id"])

    op.create_table(
        "track_loops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracks.id"), nullable=False),
        sa.Column("external_loop_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("track_id", "external_loop_id", name="uq_track_loop_external_id"),
    )
    op.create_index("ix_track_loops_track_id", "track_loops", ["track_id"])
    op.create_index("ix_track_loops_external_loop_id", "track_loops", ["external_loop_id"])

    op.create_table(
        "track_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracks.id"), nullable=False),
        sa.Column("external_track_view_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("circuit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("track_id", "external_track_view_id", name="uq_track_view_external_id"),
    )
    op.create_index("ix_track_views_track_id", "track_views", ["track_id"])
    op.create_index("ix_track_views_external_track_view_id", "track_views", ["external_track_view_id"])

    op.create_table(
        "track_view_loops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("track_view_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("track_views.id"), nullable=False),
        sa.Column("track_loop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("track_loops.id"), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("track_view_id", "sequence_index", name="uq_track_view_loop_sequence"),
    )
    op.create_index("ix_track_view_loops_track_view_id", "track_view_loops", ["track_view_id"])
    op.create_index("ix_track_view_loops_track_loop_id", "track_view_loops", ["track_loop_id"])

    op.create_table(
        "training_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sqorz_account_id", sa.String(length=255), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("sport_type", sa.String(length=64), nullable=True),
        sa.Column("start_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("sqorz_account_id", "external_event_id", name="uq_event_account_external_id"),
    )
    op.create_index("ix_training_events_sqorz_account_id", "training_events", ["sqorz_account_id"])
    op.create_index("ix_training_events_external_event_id", "training_events", ["external_event_id"])
    op.create_index("ix_training_events_event_date", "training_events", ["event_date"])

    op.create_table(
        "event_classes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "training_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_events.id"), nullable=False
        ),
        sa.Column("class_code", sa.String(length=64), nullable=False),
        sa.Column("class_name", sa.String(length=255), nullable=True),
        sa.Column("class_type", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("training_event_id", "class_code", name="uq_event_class_code"),
    )
    op.create_index("ix_event_classes_training_event_id", "event_classes", ["training_event_id"])

    op.create_table(
        "event_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "training_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_events.id"), nullable=False
        ),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracks.id"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("gate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("start_from", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("training_event_id", "track_id", name="uq_event_track"),
    )
    op.create_index("ix_event_tracks_training_event_id", "event_tracks", ["training_event_id"])
    op.create_index("ix_event_tracks_track_id", "event_tracks", ["track_id"])

    op.create_table(
        "training_laps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_track_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("event_tracks.id"), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id"), nullable=True),
        sa.Column("transponder_code", sa.String(length=255), nullable=False),
        sa.Column("class_code", sa.String(length=64), nullable=True),
        sa.Column("external_lap_id", sa.String(length=255), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_start", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("start_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_track_id", "external_lap_id", name="uq_training_lap_external_id"),
    )
    op.create_index("ix_training_laps_event_track_id", "training_laps", ["event_track_id"])
    op.create_index("ix_training_laps_athlete_id", "training_laps", ["athlete_id"])
    op.create_index("ix_training_laps_transponder_code", "training_laps", ["transponder_code"])
    op.create_index("ix_training_laps_external_lap_id", "training_laps", ["external_lap_id"])
    op.create_index("ix_training_laps_start_time", "training_laps", ["start_time"])

    op.create_table(
        "lap_segment_times",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("training_lap_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_laps.id"), nullable=False),
        sa.Column("track_loop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("track_loops.id"), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("training_lap_id", "sequence_index", name="uq_lap_segment_sequence"),
    )
    op.create_index("ix_lap_segment_times_training_lap_id", "lap_segment_times", ["training_lap_id"])
    op.create_index("ix_lap_segment_times_track_loop_id", "lap_segment_times", ["track_loop_id"])


def downgrade() -> None:
    op.drop_table("lap_segment_times")
    op.drop_table("training_laps")
    op.drop_table("event_tracks")
    op.drop_table("event_classes")
    op.drop_table("training_events")
    op.drop_table("track_view_loops")
    op.drop_table("track_views")
    op.drop_table("track_loops")
    op.drop_table("tracks")

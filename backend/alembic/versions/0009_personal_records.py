"""personal_records (computed) and manual_results

- personal_records: an athlete's best computed result per track, standard
  event and start type. Derived from training_laps; rebuilt after every sqorz
  normalization, so it can always be dropped and recomputed.
- manual_results: results the athlete types in (races, tracks without sqorz
  timing).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personal_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracks.id"), nullable=False),
        sa.Column("event_key", sa.String(length=16), nullable=False),
        sa.Column("start_type", sa.String(length=16), nullable=False),
        sa.Column("time_ms", sa.Integer(), nullable=False),
        sa.Column("achieved_on", sa.Date(), nullable=False),
        sa.Column(
            "training_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_events.id"), nullable=False
        ),
        sa.Column("training_lap_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_laps.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("athlete_id", "track_id", "event_key", "start_type", name="uq_personal_record_key"),
    )
    op.create_index("ix_personal_records_athlete_id", "personal_records", ["athlete_id"])
    op.create_index("ix_personal_records_track_id", "personal_records", ["track_id"])
    op.create_index("ix_personal_records_training_event_id", "personal_records", ["training_event_id"])
    op.create_index("ix_personal_records_training_lap_id", "personal_records", ["training_lap_id"])

    op.create_table(
        "manual_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracks.id"), nullable=True),
        sa.Column("venue", sa.String(length=255), nullable=True),
        sa.Column("event_key", sa.String(length=16), nullable=False),
        sa.Column("start_type", sa.String(length=16), nullable=False),
        sa.Column("time_ms", sa.Integer(), nullable=False),
        sa.Column("achieved_on", sa.Date(), nullable=False),
        sa.Column("is_competition", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_manual_results_athlete_id", "manual_results", ["athlete_id"])
    op.create_index("ix_manual_results_track_id", "manual_results", ["track_id"])


def downgrade() -> None:
    op.drop_index("ix_manual_results_track_id", table_name="manual_results")
    op.drop_index("ix_manual_results_athlete_id", table_name="manual_results")
    op.drop_table("manual_results")
    op.drop_index("ix_personal_records_training_lap_id", table_name="personal_records")
    op.drop_index("ix_personal_records_training_event_id", table_name="personal_records")
    op.drop_index("ix_personal_records_track_id", table_name="personal_records")
    op.drop_index("ix_personal_records_athlete_id", table_name="personal_records")
    op.drop_table("personal_records")

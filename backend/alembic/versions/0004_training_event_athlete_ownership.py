"""training_events/training_laps: per-athlete ownership

Session/lap data (training_events, event_classes, event_tracks,
training_laps, lap_segment_times) moves from a shared-by-external-id
dimension to a private per-athlete copy: training_events.athlete_id
becomes required and part of its natural key, and training_laps.athlete_id
goes from nullable (unattributed allowed) to required, since the sqorz
normalizer now resolves exactly one owning athlete per trainingDetail
before storing anything (see normalizer.py) and drops entries with no
covering TransponderAssignment window entirely, rather than storing them
unattributed.

No production data exists yet, so this truncates the affected tables
instead of backfilling an owner for pre-existing rows.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "TRUNCATE TABLE lap_segment_times, training_laps, event_tracks, event_classes, training_events CASCADE"
    )

    op.add_column(
        "training_events",
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id"), nullable=False),
    )
    op.create_index("ix_training_events_athlete_id", "training_events", ["athlete_id"])
    op.drop_constraint("uq_event_account_external_id", "training_events", type_="unique")
    op.create_unique_constraint(
        "uq_event_athlete_account_external_id",
        "training_events",
        ["athlete_id", "sqorz_account_id", "external_event_id"],
    )

    op.alter_column("training_laps", "athlete_id", nullable=False)


def downgrade() -> None:
    op.alter_column("training_laps", "athlete_id", nullable=True)

    op.drop_constraint("uq_event_athlete_account_external_id", "training_events", type_="unique")
    op.create_unique_constraint(
        "uq_event_account_external_id", "training_events", ["sqorz_account_id", "external_event_id"]
    )
    op.drop_index("ix_training_events_athlete_id", "training_events")
    op.drop_column("training_events", "athlete_id")

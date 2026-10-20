"""athlete edits: session title/notes/RPE/tags, lap exclusion and labels

- training_events: title_override (sqorz re-writes `name` on every sync, so a
  rename can't live there), notes, rpe (1-10), tags.
- training_laps: excluded (kept in its effort, never counts toward records or
  progression), label, effort_label (names the effort that lap starts).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("training_events", sa.Column("title_override", sa.String(length=255), nullable=True))
    op.add_column("training_events", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("training_events", sa.Column("rpe", sa.Integer(), nullable=True))
    op.add_column(
        "training_events", sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
    )

    op.add_column("training_laps", sa.Column("excluded", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("training_laps", sa.Column("label", sa.String(length=100), nullable=True))
    op.add_column("training_laps", sa.Column("effort_label", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("training_laps", "effort_label")
    op.drop_column("training_laps", "label")
    op.drop_column("training_laps", "excluded")
    op.drop_column("training_events", "tags")
    op.drop_column("training_events", "rpe")
    op.drop_column("training_events", "notes")
    op.drop_column("training_events", "title_override")

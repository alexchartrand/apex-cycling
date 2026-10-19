"""athlete profile fields, dated athlete_metrics, user UI preferences

- athletes.gender (never used) becomes athletes.sex: the competition
  category ("female"/"male") that UCI age categories and records split on.
- athletes.height_cm.
- athlete_metrics: dated weight/FTP/HR history, one row per athlete per day.
- users.locale / users.theme (null = never chosen, the device keeps its own).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("athletes", "gender", new_column_name="sex")
    op.add_column("athletes", sa.Column("height_cm", sa.Float(), nullable=True))

    op.add_column("users", sa.Column("locale", sa.String(length=8), nullable=True))
    op.add_column("users", sa.Column("theme", sa.String(length=16), nullable=True))

    op.create_table(
        "athlete_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("ftp_w", sa.Integer(), nullable=True),
        sa.Column("max_hr", sa.Integer(), nullable=True),
        sa.Column("resting_hr", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("athlete_id", "effective_date", name="uq_athlete_metric_date"),
    )
    op.create_index("ix_athlete_metrics_athlete_id", "athlete_metrics", ["athlete_id"])


def downgrade() -> None:
    op.drop_index("ix_athlete_metrics_athlete_id", table_name="athlete_metrics")
    op.drop_table("athlete_metrics")
    op.drop_column("users", "theme")
    op.drop_column("users", "locale")
    op.drop_column("athletes", "height_cm")
    op.alter_column("athletes", "sex", new_column_name="gender")

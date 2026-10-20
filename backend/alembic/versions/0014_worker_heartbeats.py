"""worker heartbeats: liveness and last poll of the background worker

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_poll_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_poll_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_poll_connections", sa.Integer(), nullable=True),
        sa.Column("last_poll_failures", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeats")

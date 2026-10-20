"""data-driven track settings

- tracks: indoor, elevation_m, default_temp_c (length_m already exists).
- track_loops.hidden / track_views.hidden: per-track choice of which
  checkpoints are drawn on the diagram and which views are offered, replacing
  what the frontend used to hardcode. Existing "Courbe…" loops are hidden, as
  the frontend used to do for every track.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("indoor", sa.Boolean(), nullable=True))
    op.add_column("tracks", sa.Column("elevation_m", sa.Float(), nullable=True))
    op.add_column("tracks", sa.Column("default_temp_c", sa.Float(), nullable=True))
    op.add_column("track_loops", sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("track_views", sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE track_loops SET hidden = true WHERE lower(trim(name)) LIKE 'courbe%'")


def downgrade() -> None:
    op.drop_column("track_views", "hidden")
    op.drop_column("track_loops", "hidden")
    op.drop_column("tracks", "default_temp_c")
    op.drop_column("tracks", "elevation_m")
    op.drop_column("tracks", "indoor")

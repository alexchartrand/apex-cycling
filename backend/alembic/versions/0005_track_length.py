"""tracks: add manually-set length_m

Sqorz never reports a track's total circuit length (only sparse
per-checkpoint cumulative distance on TrackLoop), so this can't be
ingested — it's a nullable, manually-set fact about the physical
facility, used by the frontend track schema diagram to place sensors
proportionally around the track.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("length_m", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("tracks", "length_m")

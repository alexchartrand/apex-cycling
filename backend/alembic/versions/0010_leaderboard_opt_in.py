"""leaderboard opt-in

The club whose leaderboard an athlete agreed to appear on.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('athletes', sa.Column('leaderboard_club_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_athletes_leaderboard_club_id', 'athletes', 'clubs', ['leaderboard_club_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_athletes_leaderboard_club_id', 'athletes', type_='foreignkey')
    op.drop_column('athletes', 'leaderboard_club_id')

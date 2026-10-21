"""goals

Target times for standard events, with the date to reach them by.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('goals',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('event_key', sa.String(length=16), nullable=False),
    sa.Column('start_type', sa.String(length=16), nullable=False),
    sa.Column('track_id', sa.Uuid(), nullable=True),
    sa.Column('target_time_ms', sa.Integer(), nullable=False),
    sa.Column('target_date', sa.Date(), nullable=False),
    sa.Column('baseline_ms', sa.Integer(), nullable=True),
    sa.Column('notes', sa.String(length=1000), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_goals_athlete_id'), 'goals', ['athlete_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_goals_athlete_id'), table_name='goals')
    op.drop_table('goals')

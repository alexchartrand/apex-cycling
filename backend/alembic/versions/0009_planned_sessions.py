"""planned sessions

Sessions put on an athlete's calendar, with planned efforts, that the
athlete marks done or links to the session actually ridden.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('planned_sessions',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('planned_date', sa.Date(), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('targets', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('training_event_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['training_event_id'], ['training_events.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_planned_sessions_athlete_id'), 'planned_sessions', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_planned_sessions_planned_date'), 'planned_sessions', ['planned_date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_planned_sessions_planned_date'), table_name='planned_sessions')
    op.drop_index(op.f('ix_planned_sessions_athlete_id'), table_name='planned_sessions')
    op.drop_table('planned_sessions')

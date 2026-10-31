"""intervals plan push

An athlete may have their planned workouts put on their Intervals.icu
calendar; each pushed plan keeps the event it became there.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0022'
down_revision: Union[str, None] = '0021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'data_source_connections',
        sa.Column('push_plans', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        'intervals_plan_events',
        sa.Column('athlete_id', sa.Uuid(), nullable=False),
        sa.Column('plan_id', sa.Uuid(), nullable=False),
        sa.Column('remote_event_id', sa.String(length=32), nullable=True),
        sa.Column('payload_hash', sa.String(length=64), nullable=True),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id'),
    )
    op.create_index(op.f('ix_intervals_plan_events_athlete_id'), 'intervals_plan_events', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_intervals_plan_events_due_at'), 'intervals_plan_events', ['due_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_intervals_plan_events_due_at'), table_name='intervals_plan_events')
    op.drop_index(op.f('ix_intervals_plan_events_athlete_id'), table_name='intervals_plan_events')
    op.drop_table('intervals_plan_events')
    op.drop_column('data_source_connections', 'push_plans')

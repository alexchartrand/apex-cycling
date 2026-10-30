"""planned session workout

A planned session can hold a copy of a workout's step tree, and the id of
the library workout it came from.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0021'
down_revision: Union[str, None] = '0020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('planned_sessions', sa.Column('workout', sa.JSON(), nullable=True))
    op.add_column('planned_sessions', sa.Column('source_workout_id', sa.Uuid(), nullable=True))
    op.create_index(
        op.f('ix_planned_sessions_source_workout_id'), 'planned_sessions', ['source_workout_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_planned_sessions_source_workout_id'), table_name='planned_sessions')
    op.drop_column('planned_sessions', 'source_workout_id')
    op.drop_column('planned_sessions', 'workout')

"""planned session activity

A plan may be linked to the recording that was ridden (a road or trainer
ride has no sqorz session), whose power answers the workout's power steps.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0023'
down_revision: Union[str, None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('planned_sessions', sa.Column('activity_id', sa.Uuid(), nullable=True))
    op.create_index('ix_planned_sessions_activity_id', 'planned_sessions', ['activity_id'], unique=False)
    op.create_foreign_key(
        'planned_sessions_activity_id_fkey', 'planned_sessions', 'activities', ['activity_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('planned_sessions_activity_id_fkey', 'planned_sessions', type_='foreignkey')
    op.drop_index('ix_planned_sessions_activity_id', table_name='planned_sessions')
    op.drop_column('planned_sessions', 'activity_id')

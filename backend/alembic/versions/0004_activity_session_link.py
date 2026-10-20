"""activity session link

Links an activity to the sqorz session it contains, with the device clock offset.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-20 13:39:52.873944

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('training_event_id', sa.Uuid(), nullable=True))
    op.add_column('activities', sa.Column('clock_offset_s', sa.Float(), server_default='0', nullable=False))
    op.add_column('activities', sa.Column('session_link_manual', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.create_index(op.f('ix_activities_training_event_id'), 'activities', ['training_event_id'], unique=False)
    op.create_foreign_key('activities_training_event_id_fkey', 'activities', 'training_events', ['training_event_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('activities_training_event_id_fkey', 'activities', type_='foreignkey')
    op.drop_index(op.f('ix_activities_training_event_id'), table_name='activities')
    op.drop_column('activities', 'session_link_manual')
    op.drop_column('activities', 'clock_offset_s')
    op.drop_column('activities', 'training_event_id')

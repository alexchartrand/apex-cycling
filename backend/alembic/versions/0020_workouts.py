"""workouts

The workout library: a user's reusable workouts, as a step tree in JSON.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0020'
down_revision: Union[str, None] = '0019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('workouts',
    sa.Column('owner_user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('tags', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    sa.Column('steps', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workouts_owner_user_id'), 'workouts', ['owner_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workouts_owner_user_id'), table_name='workouts')
    op.drop_table('workouts')

"""bike tire

The tire and its Crr belong to the bike, not to each gear. A bike takes them
from its oldest gear that had either.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bikes', sa.Column('tire', sa.String(length=100), nullable=True))
    op.add_column('bikes', sa.Column('crr', sa.Float(), nullable=True))
    op.execute(
        """
        UPDATE bikes SET tire = g.tire, crr = g.crr
        FROM (
            SELECT DISTINCT ON (bike_id) bike_id, tire, crr
            FROM gear_setups
            WHERE tire IS NOT NULL OR crr IS NOT NULL
            ORDER BY bike_id, created_at
        ) AS g
        WHERE g.bike_id = bikes.id
        """
    )
    op.drop_column('gear_setups', 'crr')
    op.drop_column('gear_setups', 'tire')


def downgrade() -> None:
    op.add_column('gear_setups', sa.Column('tire', sa.String(length=100), nullable=True))
    op.add_column('gear_setups', sa.Column('crr', sa.Float(), nullable=True))
    op.execute(
        """
        UPDATE gear_setups SET tire = bikes.tire, crr = bikes.crr
        FROM bikes WHERE bikes.id = gear_setups.bike_id
        """
    )
    op.drop_column('bikes', 'crr')
    op.drop_column('bikes', 'tire')

"""gear tire crr

The rolling resistance coefficient of a gear's tire.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('gear_setups', sa.Column('crr', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('gear_setups', 'crr')

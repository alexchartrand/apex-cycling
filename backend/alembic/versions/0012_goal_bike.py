"""goal bike

The bike a goal will be ridden on, whose weight the predicted time uses.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('goals', sa.Column('bike_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_goals_bike_id', 'goals', 'bikes', ['bike_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_goals_bike_id', 'goals', type_='foreignkey')
    op.drop_column('goals', 'bike_id')

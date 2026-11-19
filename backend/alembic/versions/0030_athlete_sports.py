"""Athletes choose their sports

`athletes.sports`: the sports the athlete does (`kinds.ATHLETE_SPORTS`), which
decide the pages and cards the app shows them. Null = not chosen yet; the
client guesses from the athlete's data.

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0030'
down_revision: Union[str, None] = '0029'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('athletes', sa.Column('sports', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('athletes', 'sports')

"""sqorz normalize tracking

An unchanged sqorz payload is no longer normalized again on every poll:
`data_source_connections` remembers when (and with which normalizer version)
it last was, and `transponder_assignments.updated_at` says when attribution
may have changed since.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0016'
down_revision: Union[str, None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('data_source_connections', sa.Column('normalized_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('data_source_connections', sa.Column('normalizer_version', sa.Integer(), nullable=True))
    op.add_column(
        'transponder_assignments',
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('transponder_assignments', 'updated_at')
    op.drop_column('data_source_connections', 'normalizer_version')
    op.drop_column('data_source_connections', 'normalized_at')

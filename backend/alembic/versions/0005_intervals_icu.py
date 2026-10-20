"""intervals.icu connections

Adds the intervals_icu data source provider and a per-run count of imported
activities for the sync history.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE data_source_provider ADD VALUE IF NOT EXISTS 'intervals_icu'")
    op.add_column('ingestion_runs', sa.Column('imported_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('ingestion_runs', 'imported_count')
    # Postgres cannot drop a value from an enum type; it stays (unused) until
    # the type itself is dropped by the baseline migration's downgrade.

"""ingestion run athlete

A sqorz sync asked for an athlete ("Sync now", adding a transponder) names
them, so a transponder handed on to someone else doesn't fill the previous
athlete's sync log with the new user's syncs.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0024'
down_revision: Union[str, None] = '0023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ingestion_runs', sa.Column('requested_for_athlete_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'ingestion_runs_requested_for_athlete_id_fkey', 'ingestion_runs', 'athletes',
        ['requested_for_athlete_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('ingestion_runs_requested_for_athlete_id_fkey', 'ingestion_runs', type_='foreignkey')
    op.drop_column('ingestion_runs', 'requested_for_athlete_id')

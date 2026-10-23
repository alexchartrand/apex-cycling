"""composite indexes

The reads that grow with the data: an athlete's sessions and rides by date,
a connection's newest ingestion runs and snapshots, the leaderboard's
records for one event on one track.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0017'
down_revision: Union[str, None] = '0016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_training_events_athlete_date', 'training_events', ['athlete_id', 'event_date'])
    op.create_index('ix_activities_athlete_start', 'activities', ['athlete_id', 'start_time'])
    op.create_index(
        'ix_ingestion_runs_connection_requested', 'ingestion_runs', ['data_source_connection_id', 'requested_at']
    )
    op.create_index('ix_raw_snapshots_ref_fetched', 'raw_snapshots', ['external_ref', 'fetched_at'])
    op.create_index('ix_personal_records_board', 'personal_records', ['track_id', 'event_key', 'start_type'])


def downgrade() -> None:
    op.drop_index('ix_personal_records_board', table_name='personal_records')
    op.drop_index('ix_raw_snapshots_ref_fetched', table_name='raw_snapshots')
    op.drop_index('ix_ingestion_runs_connection_requested', table_name='ingestion_runs')
    op.drop_index('ix_activities_athlete_start', table_name='activities')
    op.drop_index('ix_training_events_athlete_date', table_name='training_events')

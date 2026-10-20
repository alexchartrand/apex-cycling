"""activities

Imported activities (FIT/TCX/GPX uploads, later Intervals.icu and Strava): summary
row, compressed per-sample streams and mean-maximal power curve.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20 13:15:19.611438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('activities',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('source', sa.Enum('upload', 'intervals_icu', 'strava', name='activity_source'), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=True),
    sa.Column('data_source_connection_id', sa.Uuid(), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('sport', sa.String(length=64), nullable=True),
    sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('elapsed_s', sa.Float(), nullable=False),
    sa.Column('moving_s', sa.Float(), nullable=True),
    sa.Column('distance_m', sa.Float(), nullable=True),
    sa.Column('elevation_gain_m', sa.Float(), nullable=True),
    sa.Column('has_power', sa.Boolean(), nullable=False),
    sa.Column('has_heart_rate', sa.Boolean(), nullable=False),
    sa.Column('has_cadence', sa.Boolean(), nullable=False),
    sa.Column('avg_power_w', sa.Float(), nullable=True),
    sa.Column('max_power_w', sa.Float(), nullable=True),
    sa.Column('normalized_power_w', sa.Float(), nullable=True),
    sa.Column('tss', sa.Float(), nullable=True),
    sa.Column('avg_heart_rate', sa.Float(), nullable=True),
    sa.Column('max_heart_rate', sa.Float(), nullable=True),
    sa.Column('avg_cadence', sa.Float(), nullable=True),
    sa.Column('avg_speed_mps', sa.Float(), nullable=True),
    sa.Column('file_path', sa.String(length=512), nullable=True),
    sa.Column('file_format', sa.String(length=16), nullable=True),
    sa.Column('file_sha256', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['data_source_connection_id'], ['data_source_connections.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('athlete_id', 'file_sha256', name='uq_activity_athlete_file'),
    sa.UniqueConstraint('athlete_id', 'source', 'external_id', name='uq_activity_athlete_source_external')
    )
    op.create_index(op.f('ix_activities_athlete_id'), 'activities', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_activities_data_source_connection_id'), 'activities', ['data_source_connection_id'], unique=False)
    op.create_index(op.f('ix_activities_start_time'), 'activities', ['start_time'], unique=False)
    op.create_table('activity_power_curves',
    sa.Column('activity_id', sa.Uuid(), nullable=False),
    sa.Column('duration_s', sa.Integer(), nullable=False),
    sa.Column('power_w', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ),
    sa.PrimaryKeyConstraint('activity_id', 'duration_s')
    )
    op.create_table('activity_streams',
    sa.Column('activity_id', sa.Uuid(), nullable=False),
    sa.Column('sample_count', sa.Integer(), nullable=False),
    sa.Column('time_s', sa.LargeBinary(), nullable=False),
    sa.Column('power_w', sa.LargeBinary(), nullable=True),
    sa.Column('heart_rate', sa.LargeBinary(), nullable=True),
    sa.Column('cadence', sa.LargeBinary(), nullable=True),
    sa.Column('speed_mps', sa.LargeBinary(), nullable=True),
    sa.Column('distance_m', sa.LargeBinary(), nullable=True),
    sa.Column('altitude_m', sa.LargeBinary(), nullable=True),
    sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ),
    sa.PrimaryKeyConstraint('activity_id')
    )


def downgrade() -> None:
    op.drop_table('activity_streams')
    op.drop_table('activity_power_curves')
    op.drop_index(op.f('ix_activities_start_time'), table_name='activities')
    op.drop_index(op.f('ix_activities_data_source_connection_id'), table_name='activities')
    op.drop_index(op.f('ix_activities_athlete_id'), table_name='activities')
    op.drop_table('activities')
    op.execute("DROP TYPE IF EXISTS activity_source")

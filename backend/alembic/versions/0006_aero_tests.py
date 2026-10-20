"""aero tests

Saved aero runs (a session's laps in one setup) for comparing CdA between
positions and equipment. Only inputs are stored; results are computed on read.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('aero_tests',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('training_event_id', sa.Uuid(), nullable=False),
    sa.Column('track_id', sa.Uuid(), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('position', sa.String(length=100), nullable=True),
    sa.Column('helmet', sa.String(length=100), nullable=True),
    sa.Column('skinsuit', sa.String(length=100), nullable=True),
    sa.Column('bike', sa.String(length=100), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('lap_ids', sa.JSON(), nullable=True),
    sa.Column('temp_c', sa.Float(), nullable=True),
    sa.Column('elevation_m', sa.Float(), nullable=True),
    sa.Column('pressure_hpa', sa.Float(), nullable=True),
    sa.Column('humidity_pct', sa.Float(), nullable=True),
    sa.Column('rider_kg', sa.Float(), nullable=True),
    sa.Column('bike_kg', sa.Float(), nullable=True),
    sa.Column('crr', sa.Float(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ),
    sa.ForeignKeyConstraint(['training_event_id'], ['training_events.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_aero_tests_athlete_id'), 'aero_tests', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_aero_tests_training_event_id'), 'aero_tests', ['training_event_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_aero_tests_training_event_id'), table_name='aero_tests')
    op.drop_index(op.f('ix_aero_tests_athlete_id'), table_name='aero_tests')
    op.drop_table('aero_tests')

"""bikes and gear setups

Bikes and chainring/cog/rollout setups, assignable to a session or to one
effort of it (estimated cadence from lap speed).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('bikes',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('weight_kg', sa.Float(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bikes_athlete_id'), 'bikes', ['athlete_id'], unique=False)
    op.create_table('gear_setups',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('bike_id', sa.Uuid(), nullable=False),
    sa.Column('chainring_teeth', sa.Integer(), nullable=False),
    sa.Column('cog_teeth', sa.Integer(), nullable=False),
    sa.Column('rollout_mm', sa.Float(), nullable=False),
    sa.Column('tire', sa.String(length=100), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['bike_id'], ['bikes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gear_setups_athlete_id'), 'gear_setups', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_gear_setups_bike_id'), 'gear_setups', ['bike_id'], unique=False)
    op.add_column('training_events', sa.Column('gear_setup_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_training_events_gear_setup_id', 'training_events', 'gear_setups', ['gear_setup_id'], ['id'])
    op.add_column('training_laps', sa.Column('effort_gear_setup_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_training_laps_effort_gear_setup_id', 'training_laps', 'gear_setups', ['effort_gear_setup_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_training_laps_effort_gear_setup_id', 'training_laps', type_='foreignkey')
    op.drop_column('training_laps', 'effort_gear_setup_id')
    op.drop_constraint('fk_training_events_gear_setup_id', 'training_events', type_='foreignkey')
    op.drop_column('training_events', 'gear_setup_id')
    op.drop_index(op.f('ix_gear_setups_bike_id'), table_name='gear_setups')
    op.drop_index(op.f('ix_gear_setups_athlete_id'), table_name='gear_setups')
    op.drop_table('gear_setups')
    op.drop_index(op.f('ix_bikes_athlete_id'), table_name='bikes')
    op.drop_table('bikes')

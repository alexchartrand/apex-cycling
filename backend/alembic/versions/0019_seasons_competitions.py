"""seasons, competitions, calendar feed, race flag

Season start dates, the race calendar, the secret link for a phone calendar
subscription, and the athlete's "this session was a race" mark.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0019'
down_revision: Union[str, None] = '0018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('training_events', sa.Column('is_race', sa.Boolean(), server_default=sa.false(), nullable=False))

    op.create_table('seasons',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('athlete_id', 'start_date', name='uq_season_athlete_start')
    )
    op.create_index(op.f('ix_seasons_athlete_id'), 'seasons', ['athlete_id'], unique=False)

    op.create_table('competitions',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('competition_date', sa.Date(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('priority', sa.String(length=1), nullable=False),
    sa.Column('location', sa.String(length=120), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('goal_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_competitions_athlete_id'), 'competitions', ['athlete_id'], unique=False)
    op.create_index(op.f('ix_competitions_competition_date'), 'competitions', ['competition_date'], unique=False)

    op.create_table('calendar_feeds',
    sa.Column('athlete_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('athlete_id')
    )
    op.create_index(op.f('ix_calendar_feeds_token_hash'), 'calendar_feeds', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_calendar_feeds_token_hash'), table_name='calendar_feeds')
    op.drop_table('calendar_feeds')
    op.drop_index(op.f('ix_competitions_competition_date'), table_name='competitions')
    op.drop_index(op.f('ix_competitions_athlete_id'), table_name='competitions')
    op.drop_table('competitions')
    op.drop_index(op.f('ix_seasons_athlete_id'), table_name='seasons')
    op.drop_table('seasons')
    op.drop_column('training_events', 'is_race')

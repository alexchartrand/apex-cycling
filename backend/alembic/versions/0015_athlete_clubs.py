"""athlete clubs

An athlete can be on the roster of several clubs: `athletes.club_id` becomes
the `athlete_clubs` table, which also carries the leaderboard consent per club
(replacing `athletes.leaderboard_club_id`).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'athlete_clubs',
        sa.Column('athlete_id', sa.Uuid(), nullable=False),
        sa.Column('club_id', sa.Uuid(), nullable=False),
        sa.Column('leaderboard_opt_in', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id']),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id']),
        sa.PrimaryKeyConstraint('athlete_id', 'club_id'),
    )
    op.create_index(op.f('ix_athlete_clubs_club_id'), 'athlete_clubs', ['club_id'], unique=False)
    op.execute(
        """
        INSERT INTO athlete_clubs (athlete_id, club_id, leaderboard_opt_in)
        SELECT id, club_id, COALESCE(leaderboard_club_id = club_id, false)
        FROM athletes WHERE club_id IS NOT NULL
        """
    )
    op.drop_constraint('fk_athletes_leaderboard_club_id', 'athletes', type_='foreignkey')
    op.drop_column('athletes', 'leaderboard_club_id')
    op.drop_index(op.f('ix_athletes_club_id'), table_name='athletes')
    op.drop_constraint('athletes_club_id_fkey', 'athletes', type_='foreignkey')
    op.drop_column('athletes', 'club_id')


def downgrade() -> None:
    op.add_column('athletes', sa.Column('club_id', sa.Uuid(), nullable=True))
    op.add_column('athletes', sa.Column('leaderboard_club_id', sa.Uuid(), nullable=True))
    # One club per profile again: keep the one joined first.
    op.execute(
        """
        UPDATE athletes SET club_id = first.club_id
        FROM (
            SELECT DISTINCT ON (athlete_id) athlete_id, club_id
            FROM athlete_clubs ORDER BY athlete_id, joined_at, club_id
        ) AS first
        WHERE athletes.id = first.athlete_id
        """
    )
    op.execute(
        """
        UPDATE athletes SET leaderboard_club_id = athlete_clubs.club_id
        FROM athlete_clubs
        WHERE athlete_clubs.athlete_id = athletes.id
          AND athlete_clubs.club_id = athletes.club_id
          AND athlete_clubs.leaderboard_opt_in
        """
    )
    op.create_foreign_key('athletes_club_id_fkey', 'athletes', 'clubs', ['club_id'], ['id'])
    op.create_index(op.f('ix_athletes_club_id'), 'athletes', ['club_id'], unique=False)
    op.create_foreign_key('fk_athletes_leaderboard_club_id', 'athletes', 'clubs', ['leaderboard_club_id'], ['id'])
    op.drop_index(op.f('ix_athlete_clubs_club_id'), table_name='athlete_clubs')
    op.drop_table('athlete_clubs')

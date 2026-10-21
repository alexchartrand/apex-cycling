"""track facility profile

A hand-set display name for tracks (sqorz calls every venue's full lap "Tour
complet") and the facility's location and build.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tracks', sa.Column('sqorz_name', sa.String(length=255), nullable=True))
    op.add_column('tracks', sa.Column('name_is_custom', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('tracks', sa.Column('city', sa.String(length=255), nullable=True))
    op.add_column('tracks', sa.Column('region', sa.String(length=255), nullable=True))
    op.add_column('tracks', sa.Column('country', sa.String(length=255), nullable=True))
    op.add_column('tracks', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('tracks', sa.Column('longitude', sa.Float(), nullable=True))
    op.add_column('tracks', sa.Column('width_m', sa.Float(), nullable=True))
    op.add_column('tracks', sa.Column('surface', sa.String(length=255), nullable=True))
    op.add_column('tracks', sa.Column('bank_straight_deg', sa.Float(), nullable=True))
    op.add_column('tracks', sa.Column('bank_curve_deg', sa.Float(), nullable=True))
    op.add_column('tracks', sa.Column('notes', sa.Text(), nullable=True))
    # Until now `name` was always the sqorz name.
    op.execute('UPDATE tracks SET sqorz_name = name')


def downgrade() -> None:
    for column in ('notes', 'bank_curve_deg', 'bank_straight_deg', 'surface', 'width_m', 'longitude', 'latitude',
                   'country', 'region', 'city', 'name_is_custom', 'sqorz_name'):
        op.drop_column('tracks', column)

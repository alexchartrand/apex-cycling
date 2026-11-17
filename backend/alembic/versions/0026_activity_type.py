"""activity type

`activities.activity_type` (cycling / track_cycling / indoor_cycling /
strength / other, app/activities/kinds.py) guessed from the source's sport,
and `activity_type_manual` for a type the athlete chose. Existing rows are
classified from their stored sport here; `python -m app.activities.cli
reclassify` refines FIT uploads from their sub-sport.

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0026'
down_revision: Union[str, None] = '0025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'activities', sa.Column('activity_type', sa.String(length=32), server_default='cycling', nullable=False)
    )
    op.add_column(
        'activities',
        sa.Column('activity_type_manual', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute(
        """
        UPDATE activities SET activity_type = CASE
            WHEN training_event_id IS NOT NULL THEN 'track_cycling'
            WHEN sport IS NULL THEN 'cycling'
            WHEN lower(sport) IN ('virtualride', 'indoor_cycling', 'virtual_activity') THEN 'indoor_cycling'
            WHEN lower(sport) IN ('trackride', 'track_cycling') THEN 'track_cycling'
            WHEN lower(sport) IN ('weighttraining', 'training', 'strength_training', 'fitness_equipment', 'crossfit', 'workout')
                THEN 'strength'
            WHEN lower(sport) LIKE '%ride%' OR lower(sport) LIKE '%cycl%' OR lower(sport) LIKE '%bik%'
                OR lower(sport) IN ('velomobile', 'handcycle') THEN 'cycling'
            ELSE 'other'
        END
        """
    )


def downgrade() -> None:
    op.drop_column('activities', 'activity_type_manual')
    op.drop_column('activities', 'activity_type')

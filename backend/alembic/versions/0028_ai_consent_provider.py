"""AI coach consent names its provider

`ai_coach_access.consent_provider`: the model provider the athlete agreed to
send their data to. Consent given so far was for Mistral AI.

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0028'
down_revision: Union[str, None] = '0027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ai_coach_access', sa.Column('consent_provider', sa.String(length=32), nullable=True))
    op.execute("UPDATE ai_coach_access SET consent_provider = 'mistral' WHERE consent_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column('ai_coach_access', 'consent_provider')

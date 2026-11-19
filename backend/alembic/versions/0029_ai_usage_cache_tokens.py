"""AI usage records prompt-cache tokens

`ai_usage.cache_read_tokens` / `cache_write_tokens`: the parts of
`prompt_tokens` served from or written to the provider's prompt cache
(Anthropic prices them at a fraction / 1.25× of input), so the admin's cost
estimate matches the bill. Rows from before this are 0 (priced as input).

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0029'
down_revision: Union[str, None] = '0028'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ai_usage', sa.Column('cache_read_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('ai_usage', sa.Column('cache_write_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    op.drop_column('ai_usage', 'cache_write_tokens')
    op.drop_column('ai_usage', 'cache_read_tokens')

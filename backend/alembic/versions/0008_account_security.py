"""account security: password reset tokens, session revocation, deletable users

- users.credentials_changed_at: tokens issued before it are rejected, so a
  password change/reset signs every other session out.
- password_reset_tokens: hashed, expiring, single-use reset links.
- transponder_assignments.created_by_user_id and
  coach_athletes.initiated_by_user_id become nullable, so deleting an
  account can drop the reference from rows other people own instead of
  deleting those rows.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("credentials_changed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.alter_column("transponder_assignments", "created_by_user_id", nullable=True)
    op.alter_column("coach_athletes", "initiated_by_user_id", nullable=True)


def downgrade() -> None:
    # Fails if a deleted account already left nulls behind; there's no
    # user to put back in those rows.
    op.alter_column("coach_athletes", "initiated_by_user_id", nullable=False)
    op.alter_column("transponder_assignments", "created_by_user_id", nullable=False)

    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "credentials_changed_at")

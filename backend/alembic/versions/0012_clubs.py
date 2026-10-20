"""clubs: invite links and the club <-> sqorz account link

- club_invites: hashed single/multi-use links that add someone to a club in a
  given role.
- club_sqorz_accounts: which sqorz facilities a club's admins may edit the
  tracks of.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "club_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clubs.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("athlete", "coach", "club_admin", name="club_role", create_type=False),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_club_invites_club_id", "club_invites", ["club_id"])

    op.create_table(
        "club_sqorz_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clubs.id"), nullable=False),
        sa.Column("sqorz_account_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("club_id", "sqorz_account_id", name="uq_club_sqorz_account"),
    )
    op.create_index("ix_club_sqorz_accounts_club_id", "club_sqorz_accounts", ["club_id"])
    op.create_index("ix_club_sqorz_accounts_sqorz_account_id", "club_sqorz_accounts", ["sqorz_account_id"])


def downgrade() -> None:
    op.drop_table("club_sqorz_accounts")
    op.drop_table("club_invites")

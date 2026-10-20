"""session comments: the coach <-> athlete thread on a session, and read markers

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "training_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_events.id"), nullable=False
        ),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_session_comments_training_event_id", "session_comments", ["training_event_id"])
    op.create_index("ix_session_comments_author_user_id", "session_comments", ["author_user_id"])

    op.create_table(
        "session_comment_reads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "training_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_events.id"), nullable=False
        ),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "training_event_id", name="uq_session_comment_read"),
    )
    op.create_index("ix_session_comment_reads_user_id", "session_comment_reads", ["user_id"])
    op.create_index("ix_session_comment_reads_training_event_id", "session_comment_reads", ["training_event_id"])


def downgrade() -> None:
    op.drop_table("session_comment_reads")
    op.drop_table("session_comments")

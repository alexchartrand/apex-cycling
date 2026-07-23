"""identity and tenancy: users, athletes, clubs, club_memberships, coach_athletes

Revision ID: 0001
Revises:
Create Date: 2026-07-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "clubs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_clubs_slug", "clubs", ["slug"], unique=True)

    op.create_table(
        "athletes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clubs.id"), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("birthdate", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_athletes_user_id", "athletes", ["user_id"], unique=True)
    op.create_index("ix_athletes_club_id", "athletes", ["club_id"])

    op.create_table(
        "club_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clubs.id"), nullable=False),
        sa.Column(
            "role",
            sa.Enum("athlete", "coach", "club_admin", name="club_role"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "club_id", name="uq_club_membership_user_club"),
    )
    op.create_index("ix_club_memberships_user_id", "club_memberships", ["user_id"])
    op.create_index("ix_club_memberships_club_id", "club_memberships", ["club_id"])

    op.create_table(
        "coach_athletes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("coach_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("initiated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending_athlete_acceptance",
                "pending_coach_acceptance",
                "active",
                "revoked",
                name="coach_athlete_status",
            ),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("coach_user_id", "athlete_id", name="uq_coach_athlete"),
    )
    op.create_index("ix_coach_athletes_coach_user_id", "coach_athletes", ["coach_user_id"])
    op.create_index("ix_coach_athletes_athlete_id", "coach_athletes", ["athlete_id"])


def downgrade() -> None:
    op.drop_table("coach_athletes")
    op.drop_table("club_memberships")
    op.drop_index("ix_athletes_club_id", table_name="athletes")
    op.drop_index("ix_athletes_user_id", table_name="athletes")
    op.drop_table("athletes")
    op.drop_index("ix_clubs_slug", table_name="clubs")
    op.drop_table("clubs")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    postgresql.ENUM(name="coach_athlete_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="club_role").drop(op.get_bind(), checkfirst=True)

"""sqorz raw ingestion: data_source_connections, transponder_assignments, ingestion_runs, raw_snapshots

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_source_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.Enum("sqorz", "strava", "garmin", name="data_source_provider"), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id"), nullable=True),
        sa.Column("credentials", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", name="data_source_connection_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sqorz_account_id", sa.String(length=255), nullable=True),
        sa.Column("sqorz_account_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "external_id", name="uq_connection_provider_external_id"),
    )
    op.create_index("ix_data_source_connections_external_id", "data_source_connections", ["external_id"])
    op.create_index("ix_data_source_connections_athlete_id", "data_source_connections", ["athlete_id"])

    op.create_table(
        "transponder_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column(
            "data_source_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_source_connections.id"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transponder_assignments_athlete_id", "transponder_assignments", ["athlete_id"])
    op.create_index(
        "ix_transponder_assignments_connection_id", "transponder_assignments", ["data_source_connection_id"]
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "data_source_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_source_connections.id"),
            nullable=False,
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "success", "failed", name="ingestion_run_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ingestion_runs_connection_id", "ingestion_runs", ["data_source_connection_id"])

    op.create_table(
        "raw_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ingestion_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.id"), nullable=False),
        sa.Column("provider", sa.Enum("sqorz", "strava", "garmin", name="data_source_provider"), nullable=False),
        sa.Column("external_ref", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_raw_snapshots_ingestion_run_id", "raw_snapshots", ["ingestion_run_id"])
    op.create_index("ix_raw_snapshots_external_ref", "raw_snapshots", ["external_ref"])
    op.create_index("ix_raw_snapshots_content_hash", "raw_snapshots", ["content_hash"])


def downgrade() -> None:
    op.drop_table("raw_snapshots")
    op.drop_table("ingestion_runs")
    op.drop_table("transponder_assignments")
    op.drop_table("data_source_connections")
    postgresql.ENUM(name="ingestion_run_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="data_source_connection_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="data_source_provider").drop(op.get_bind(), checkfirst=True)

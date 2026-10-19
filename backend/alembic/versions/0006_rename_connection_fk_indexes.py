"""rename two FK indexes to match the model-derived names

0002 hand-named the `data_source_connection_id` indexes on
ingestion_runs / transponder_assignments `ix_*_connection_id`, while
the models' `index=True` derives `ix_*_data_source_connection_id`.
Same column, same index — renamed only so `alembic check` reports no
drift and can guard CI against models changing without a migration.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RENAMES = [
    ("ix_ingestion_runs_connection_id", "ix_ingestion_runs_data_source_connection_id"),
    ("ix_transponder_assignments_connection_id", "ix_transponder_assignments_data_source_connection_id"),
]


def upgrade() -> None:
    for old, new in _RENAMES:
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")


def downgrade() -> None:
    for old, new in _RENAMES:
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")

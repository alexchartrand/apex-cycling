"""SQLite never enforces enum values, so a mismatch between a Python enum's
`.name` (what SQLAlchemy sends by default) and the lowercase values the
Postgres migrations declare only surfaces against a real Postgres DB — as
happened once this was actually run against Postgres. Every enum column
must set `values_callable` so SQLAlchemy emits `.value`, not `.name`.
"""

from app.activities.models import Activity, ActivitySource
from app.athletes.models import CoachAthlete, CoachAthleteStatus
from app.clubs.models import ClubInvite, ClubMembership, ClubRole
from app.connections.models import (
    DataSourceConnection,
    DataSourceConnectionStatus,
    DataSourceProvider,
    IngestionRun,
    IngestionRunStatus,
    RawSnapshot,
)

CASES = [
    (Activity, "source", ActivitySource),
    (ClubMembership, "role", ClubRole),
    (ClubInvite, "role", ClubRole),
    (CoachAthlete, "status", CoachAthleteStatus),
    (DataSourceConnection, "provider", DataSourceProvider),
    (DataSourceConnection, "status", DataSourceConnectionStatus),
    (RawSnapshot, "provider", DataSourceProvider),
    (IngestionRun, "status", IngestionRunStatus),
]


def test_enum_columns_use_member_values_not_names():
    for model_cls, column_name, enum_cls in CASES:
        column = model_cls.__table__.c[column_name]
        assert column.type.enums == [member.value for member in enum_cls], (
            f"{model_cls.__name__}.{column_name} must map to enum .value, not .name "
            "(add values_callable=lambda e: [m.value for m in e])"
        )

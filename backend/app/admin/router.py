from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schemas import AdminCounts, AdminOverview, AdminUserRow, FailedRun, WorkerStatus
from app.athletes.models import Athlete
from app.auth.deps import require_platform_admin
from app.auth.models import User
from app.clubs.models import Club
from app.connections.models import (
    DataSourceConnection,
    DataSourceConnectionStatus,
    IngestionRun,
    IngestionRunStatus,
)
from app.db.session import get_db
from app.ops.heartbeat import INGESTION_WORKER, STALE_AFTER_SECONDS
from app.ops.models import WorkerHeartbeat

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_platform_admin)])

RECENT_USERS = 25
FAILED_RUNS = 25


def worker_status(row: WorkerHeartbeat | None, now: datetime) -> WorkerStatus:
    if row is None:
        return WorkerStatus(state="never")
    last_seen = row.last_seen_at
    if last_seen.tzinfo is None:  # SQLite hands back naive datetimes
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    stale = (now - last_seen).total_seconds() > STALE_AFTER_SECONDS
    return WorkerStatus(
        state="stale" if stale else "ok",
        started_at=row.started_at,
        last_seen_at=row.last_seen_at,
        last_poll_started_at=row.last_poll_started_at,
        last_poll_finished_at=row.last_poll_finished_at,
        last_poll_connections=row.last_poll_connections,
        last_poll_failures=row.last_poll_failures,
        last_error=row.last_error,
    )


@router.get("/overview", response_model=AdminOverview)
async def overview(db: AsyncSession = Depends(get_db)) -> AdminOverview:
    async def count(model) -> int:
        return await db.scalar(select(func.count()).select_from(model)) or 0

    counts = AdminCounts(
        users=await count(User),
        athletes=await count(Athlete),
        clubs=await count(Club),
        active_transponders=await db.scalar(
            select(func.count())
            .select_from(DataSourceConnection)
            .where(DataSourceConnection.status == DataSourceConnectionStatus.ACTIVE)
        )
        or 0,
    )

    user_rows = await db.execute(
        select(User, Athlete.display_name)
        .outerjoin(Athlete, Athlete.user_id == User.id)
        .order_by(User.created_at.desc())
        .limit(RECENT_USERS)
    )
    recent_users = [
        AdminUserRow(
            id=user.id,
            email=user.email,
            display_name=display_name,
            created_at=user.created_at,
            is_active=user.is_active,
            is_platform_admin=user.is_platform_admin,
        )
        for user, display_name in user_rows
    ]

    run_rows = await db.execute(
        select(IngestionRun, DataSourceConnection.external_id)
        .join(DataSourceConnection, DataSourceConnection.id == IngestionRun.data_source_connection_id)
        .where(IngestionRun.status == IngestionRunStatus.FAILED)
        .order_by(IngestionRun.requested_at.desc())
        .limit(FAILED_RUNS)
    )
    failed_runs = [
        FailedRun(
            id=run.id,
            transponder=external_id,
            requested_at=run.requested_at,
            http_status=run.http_status,
            error_message=run.error_message,
        )
        for run, external_id in run_rows
    ]

    worker = worker_status(await db.get(WorkerHeartbeat, INGESTION_WORKER), datetime.now(timezone.utc))
    return AdminOverview(worker=worker, counts=counts, recent_users=recent_users, failed_runs=failed_runs)

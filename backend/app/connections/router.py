import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.connections.models import DataSourceConnection, TransponderAssignment
from app.connections.schemas import (
    IngestionRunRead,
    IngestionRunWithSourceRead,
    TransponderAssignmentCreate,
    TransponderAssignmentRead,
)
from app.connections.service import (
    OverlappingAssignmentError,
    create_transponder_assignment,
    list_ingestion_runs_for_athlete,
    stop_transponder_assignment,
)
from app.db.session import get_db
from app.ingestion.sqorz.factory import build_sqorz_ingestion_service

router = APIRouter(prefix="/athletes/{athlete_id}/transponder-assignments", tags=["connections"])
ingestion_runs_router = APIRouter(prefix="/athletes/{athlete_id}/ingestion-runs", tags=["connections"])


async def _to_read_model(db: AsyncSession, assignment: TransponderAssignment) -> TransponderAssignmentRead:
    connection = await db.get(DataSourceConnection, assignment.data_source_connection_id)
    return TransponderAssignmentRead(
        id=assignment.id,
        athlete_id=assignment.athlete_id,
        transponder_code=connection.external_id,
        start_date=assignment.start_date,
        end_date=assignment.end_date,
        notes=assignment.notes,
        created_at=assignment.created_at,
    )


@router.post("", response_model=TransponderAssignmentRead, status_code=status.HTTP_201_CREATED)
async def report_transponder_usage(
    athlete_id: uuid.UUID,
    payload: TransponderAssignmentCreate,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransponderAssignmentRead:
    try:
        assignment = await create_transponder_assignment(
            db,
            athlete_id=athlete.id,
            transponder_code=payload.transponder_code,
            start_date=payload.start_date,
            end_date=payload.end_date,
            created_by_user_id=current_user.id,
            notes=payload.notes,
        )
    except OverlappingAssignmentError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await db.commit()

    if payload.import_now:
        await build_sqorz_ingestion_service(db).ingest_by_id(assignment.data_source_connection_id)

    return await _to_read_model(db, assignment)


@router.get("", response_model=list[TransponderAssignmentRead])
async def list_transponder_assignments(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[TransponderAssignmentRead]:
    assignments = await db.scalars(
        select(TransponderAssignment)
        .where(TransponderAssignment.athlete_id == athlete.id)
        .order_by(TransponderAssignment.start_date.desc())
    )
    return [await _to_read_model(db, a) for a in assignments]


@router.post("/{assignment_id}/import", response_model=IngestionRunRead)
async def import_transponder_assignment_now(
    athlete_id: uuid.UUID,
    assignment_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> IngestionRunRead:
    assignment = await db.get(TransponderAssignment, assignment_id)
    if assignment is None or assignment.athlete_id != athlete.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transponder assignment not found")

    run = await build_sqorz_ingestion_service(db).ingest_by_id(assignment.data_source_connection_id, force=True)
    return IngestionRunRead.model_validate(run)


@router.post("/{assignment_id}/stop", response_model=TransponderAssignmentRead)
async def stop_transponder_assignment_route(
    athlete_id: uuid.UUID,
    assignment_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> TransponderAssignmentRead:
    assignment = await stop_transponder_assignment(db, athlete_id=athlete.id, assignment_id=assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transponder assignment not found")

    await db.commit()
    return await _to_read_model(db, assignment)


@ingestion_runs_router.get("", response_model=list[IngestionRunWithSourceRead])
async def list_ingestion_runs(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[IngestionRunWithSourceRead]:
    rows = await list_ingestion_runs_for_athlete(db, athlete_id=athlete.id)
    return [
        IngestionRunWithSourceRead(
            id=run.id,
            status=run.status,
            requested_at=run.requested_at,
            completed_at=run.completed_at,
            http_status=run.http_status,
            error_message=run.error_message,
            transponder_code=transponder_code,
        )
        for run, transponder_code in rows
    ]

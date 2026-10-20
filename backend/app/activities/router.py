import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities import service
from app.activities.models import Activity, ActivityPowerCurve, ActivityStream
from app.activities.parsers import ActivityParseError
from app.activities.schemas import ActivityRead, UploadResult
from app.activities.storage import delete_originals_after_commit
from app.athletes.coaching import speaks_for_athlete
from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db

router = APIRouter(prefix="/athletes/{athlete_id}/activities", tags=["activities"])

MAX_FILES_PER_UPLOAD = 20


async def _require_data_owner(db: AsyncSession, user: User, athlete: Athlete) -> None:
    """Adding and removing activities is for the athlete (or the club admins
    of a managed athlete); coaches read what the athlete shares."""
    if not await speaks_for_athlete(db, user, athlete):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the athlete can change their activities")


async def _find(db: AsyncSession, athlete: Athlete, viewer: User, activity_id: uuid.UUID) -> Activity:
    activity = await db.scalar(service.visible_activities(athlete, viewer).where(Activity.id == activity_id))
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    return activity


@router.post("/upload", response_model=list[UploadResult])
@limiter.limit("20/minute")
async def upload_activities(
    request: Request,
    files: list[UploadFile],
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UploadResult]:
    """Imports FIT, TCX or GPX files. Each file succeeds or fails on its own:
    the answer lists a result per file."""
    await _require_data_owner(db, current_user, athlete)
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"At most {MAX_FILES_PER_UPLOAD} files at once")

    limit = get_settings().max_activity_file_bytes
    results: list[UploadResult] = []
    for upload in files:
        name = upload.filename or "file"
        try:
            content = await upload.read(limit + 1)
            outcome = await service.import_activity_file(db, athlete.id, content)
        except ActivityParseError as exc:
            results.append(UploadResult(filename=name, status="failed", error=str(exc)))
            continue
        results.append(
            UploadResult(filename=name, status=outcome.status, activity=ActivityRead.model_validate(outcome.activity))
        )
    await db.commit()
    return results


@router.get("", response_model=list[ActivityRead])
async def list_activities(
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Activity]:
    """Newest first. `start`/`end` bound the activity's start time."""
    query = service.visible_activities(athlete, current_user)
    if start is not None:
        query = query.where(Activity.start_time >= start)
    if end is not None:
        query = query.where(Activity.start_time < end)
    return list(await db.scalars(query.order_by(Activity.start_time.desc()).limit(limit).offset(offset)))


@router.get("/{activity_id}", response_model=ActivityRead)
async def get_activity(
    activity_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Activity:
    return await _find(db, athlete, current_user, activity_id)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    activity_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _require_data_owner(db, current_user, athlete)
    activity = await _find(db, athlete, current_user, activity_id)
    if activity.file_path:
        delete_originals_after_commit(db, [activity.file_path])
    await db.execute(delete(ActivityPowerCurve).where(ActivityPowerCurve.activity_id == activity.id))
    await db.execute(delete(ActivityStream).where(ActivityStream.activity_id == activity.id))
    await db.delete(activity)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities import downsample, fusion_service, metrics_service, service, streams
from app.activities.models import Activity, ActivitySource, ActivityStream
from app.activities.parsers import ActivityParseError
from app.activities.schemas import (
    ActivityAnalysis,
    ActivityRead,
    ActivityStreamsRead,
    ActivityUpdate,
    PowerCurvePoint,
    PowerProfile,
    SessionLinkWrite,
    SessionSuggestion,
    TrainingLoadRead,
    UploadResult,
)
from app.athletes.coaching import speaks_for_athlete
from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.training.models import TrainingEvent

router = APIRouter(prefix="/athletes/{athlete_id}/activities", tags=["activities"])
analysis_router = APIRouter(prefix="/athletes/{athlete_id}", tags=["activities"])

MAX_FILES_PER_UPLOAD = 20
_SOURCE_URLS = {
    ActivitySource.STRAVA: "https://www.strava.com/activities/{id}",
    ActivitySource.INTERVALS_ICU: "https://intervals.icu/activities/{id}",
}


async def _require_data_owner(db: AsyncSession, user: User, athlete: Athlete) -> None:
    """Adding and removing activities is for the athlete (or the club admins
    of a managed athlete); coaches read what the athlete shares."""
    if not await speaks_for_athlete(db, user, athlete):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the athlete can change their activities")


async def _reads(db: AsyncSession, activities: list[Activity]) -> list[ActivityRead]:
    """API shape of activities, with the linked session's public id."""
    event_ids = {a.training_event_id for a in activities if a.training_event_id}
    external_ids: dict[uuid.UUID, str] = {}
    if event_ids:
        rows = await db.execute(
            select(TrainingEvent.id, TrainingEvent.external_event_id).where(TrainingEvent.id.in_(event_ids))
        )
        external_ids = {event_id: external_id for event_id, external_id in rows}
    reads = []
    for activity in activities:
        read = ActivityRead.model_validate(activity)
        read.external_event_id = external_ids.get(activity.training_event_id)
        template = _SOURCE_URLS.get(activity.source)
        read.external_url = template.format(id=activity.external_id) if template and activity.external_id else None
        reads.append(read)
    return reads


async def _find(db: AsyncSession, athlete: Athlete, viewer: User, activity_id: uuid.UUID) -> Activity:
    activity = await db.scalar(service.visible_activities(athlete, viewer).where(Activity.id == activity_id))
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    return activity


@router.post("/upload", response_model=list[UploadResult])
@limiter.limit("40/minute")
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
        results.append(UploadResult(filename=name, status=outcome.status, activity=(await _reads(db, [outcome.activity]))[0]))
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
) -> list[ActivityRead]:
    """Newest first. `start`/`end` bound the activity's start time."""
    query = service.visible_activities(athlete, current_user)
    if start is not None:
        query = query.where(Activity.start_time >= start)
    if end is not None:
        query = query.where(Activity.start_time < end)
    rows = list(await db.scalars(query.order_by(Activity.start_time.desc()).limit(limit).offset(offset)))
    return await _reads(db, rows)


@router.get("/{activity_id}", response_model=ActivityRead)
async def get_activity(
    activity_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityRead:
    return (await _reads(db, [await _find(db, athlete, current_user, activity_id)]))[0]


@router.patch("/{activity_id}", response_model=ActivityRead)
async def update_activity(
    activity_id: uuid.UUID,
    payload: ActivityUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityRead:
    """Rename an activity, add notes, rate the effort (the rating is what
    counts toward training load when there is no power)."""
    await _require_data_owner(db, current_user, athlete)
    activity = await _find(db, athlete, current_user, activity_id)
    for field in payload.model_fields_set:
        setattr(activity, field, getattr(payload, field))
    await db.commit()
    return (await _reads(db, [activity]))[0]


@router.get("/{activity_id}/streams", response_model=ActivityStreamsRead)
async def get_activity_streams(
    activity_id: uuid.UUID,
    max_points: int = Query(default=1200, ge=50, le=5000),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityStreamsRead:
    """The recording thinned for a chart: buckets of consecutive samples are
    averaged (power, heart rate, cadence, speed) or represented by their last
    reading (time, distance, altitude)."""
    activity = await _find(db, athlete, current_user, activity_id)
    stream = await db.get(ActivityStream, activity.id)
    if stream is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No samples stored for this activity")
    size = downsample.bucket_size(stream.sample_count, max_points)
    thinned = {
        channel: downsample.downsample(channel, streams.unpack(channel, blob), size) if (blob := getattr(stream, channel)) else None
        for channel in streams.CHANNELS
    }
    return ActivityStreamsRead(sample_count=stream.sample_count, point_count=len(thinned["time_s"]), **thinned)


@router.get("/{activity_id}/analysis", response_model=ActivityAnalysis)
async def get_activity_analysis(
    activity_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityAnalysis:
    """Intensity factor, W/kg, work, time in power and heart-rate zones and the
    activity's own power curve, using the FTP, weight and max HR in force that day."""
    return await metrics_service.analyze_activity(db, athlete, await _find(db, athlete, current_user, activity_id))


@router.get("/{activity_id}/session/suggestion", response_model=SessionSuggestion)
async def session_suggestion(
    activity_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionSuggestion:
    """The sqorz session this ride appears to contain and the device clock
    offset its lap speeds imply, without changing anything."""
    return await fusion_service.suggest(db, await _find(db, athlete, current_user, activity_id))


@router.put("/{activity_id}/session", response_model=ActivityRead)
async def link_session(
    activity_id: uuid.UUID,
    payload: SessionLinkWrite,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityRead:
    """Links the ride to a sqorz session (or adjusts the clock offset of an
    existing link). A link made here is never undone automatically."""
    await _require_data_owner(db, current_user, athlete)
    activity = await _find(db, athlete, current_user, activity_id)
    event = await db.scalar(
        select(TrainingEvent).where(
            TrainingEvent.athlete_id == athlete.id, TrainingEvent.external_event_id == payload.external_event_id
        )
    )
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    await fusion_service.set_manual_link(db, activity, event, payload.clock_offset_s)
    await db.commit()
    return (await _reads(db, [activity]))[0]


@router.delete("/{activity_id}/session", response_model=ActivityRead)
async def unlink_session(
    activity_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityRead:
    """Detaches the ride from its session; auto-linking won't reattach it."""
    await _require_data_owner(db, current_user, athlete)
    activity = await _find(db, athlete, current_user, activity_id)
    fusion_service.unlink(activity)
    await db.commit()
    return (await _reads(db, [activity]))[0]


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    activity_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _require_data_owner(db, current_user, athlete)
    activity = await _find(db, athlete, current_user, activity_id)
    await service.delete_activities(db, [activity])
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@analysis_router.get("/training-load", response_model=TrainingLoadRead)
async def get_training_load(
    through: date | None = Query(default=None, description="Last day shown; defaults to today"),
    days: int = Query(default=180, ge=1, le=730),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrainingLoadRead:
    """Fitness (CTL), fatigue (ATL) and form (TSB) per day. A day's load is
    power-based TSS where there is power and an FTP, effort rating (RPE) x
    duration elsewhere — rated sqorz sessions included."""
    zone = await metrics_service.athlete_timezone(db, athlete)
    through = through or datetime.now(zone).date()
    return await metrics_service.training_load(db, athlete, current_user, through=through, days=days)


@analysis_router.get("/power-curve", response_model=list[PowerCurvePoint])
async def get_power_curve(
    start: datetime | None = None,
    end: datetime | None = None,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PowerCurvePoint]:
    """Best power per duration over the range (`start` inclusive, `end`
    exclusive), each with the activity that set it. Call twice to compare
    ranges."""
    return await metrics_service.best_power_curve(db, athlete, current_user, start=start, end=end)


@analysis_router.get("/power-profile", response_model=PowerProfile)
async def get_power_profile(
    days: int = Query(default=90, ge=14, le=365),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PowerProfile:
    """Critical power, W′ and an FTP suggestion from the last `days` days."""
    return await metrics_service.power_profile(db, athlete, current_user, days=days)

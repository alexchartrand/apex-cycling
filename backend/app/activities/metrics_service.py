"""Persists power metrics and answers the load / power-curve questions.

The arithmetic lives in `app/analysis/metrics.py`; this module is the part
that knows about activities, FTP history, sqorz sessions and time zones.
"""

import asyncio
import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities import streams
from app.activities.models import Activity, ActivityPowerCurve, ActivitySource, ActivityStream
from app.activities.schemas import (
    ActivityAnalysis,
    CurvePoint,
    PowerCurvePoint,
    TrainingLoadDay,
    TrainingLoadRead,
    ZoneDistribution,
)
from app.analysis import metrics
from app.athletes.models import Athlete, AthleteMetric
from app.athletes.service import DatedValue, metrics_as_of
from app.auth.models import User
from app.clubs.models import Club
from app.training.models import TrainingEvent

# A sqorz session window longer than this is a whole-day booking, not training time.
_MAX_SESSION_S = 6 * 3600


async def athlete_timezone(db: AsyncSession, athlete: Athlete) -> ZoneInfo:
    """The club's zone: an evening ride must land on the day it was ridden, not
    on tomorrow's UTC date. Athletes outside a club fall back to UTC."""
    name = await db.scalar(select(Club.timezone).where(Club.id == athlete.club_id)) if athlete.club_id else None
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def local_day(moment: datetime, zone: ZoneInfo) -> date:
    return moment.astimezone(zone).date()


def visible_conditions(athlete: Athlete, viewer: User) -> list:
    """Row filters for the activities `viewer` may see of `athlete`. Strava's
    API terms only allow a user's Strava data to be shown to that user, so
    anyone else (coach, club admin) doesn't get Strava-sourced ones."""
    conditions = [Activity.athlete_id == athlete.id]
    if athlete.user_id != viewer.id:
        conditions.append(Activity.source != ActivitySource.STRAVA)
    return conditions


# --- per activity ----------------------------------------------------------


def _ftp_on(metric_rows: Sequence[AthleteMetric], day: date) -> float | None:
    """The FTP in force on `day`; before the first one was entered, that first
    one (rides older than the athlete's records still deserve a TSS)."""
    ftp: DatedValue | None = metrics_as_of(list(metric_rows), day)["ftp_w"]
    if ftp is None:
        entered = [row for row in metric_rows if row.ftp_w is not None]
        if entered:
            return float(min(entered, key=lambda row: row.effective_date).ftp_w)
        return None
    return float(ftp.value)


def _tss(activity: Activity, ftp_w: float | None) -> float | None:
    if activity.normalized_power_w is None or ftp_w is None:
        return None
    return metrics.training_stress_score(activity.moving_s or activity.elapsed_s, activity.normalized_power_w, ftp_w)


async def _metric_rows(db: AsyncSession, athlete_id: uuid.UUID) -> list[AthleteMetric]:
    return list(await db.scalars(select(AthleteMetric).where(AthleteMetric.athlete_id == athlete_id)))


def compute_power_metrics(
    time_s: Sequence[float], power: Sequence[float | None]
) -> tuple[dict[int, float], float | None]:
    """(mean-maximal power curve, normalized power) of a recording. The curve
    counts a stop as 0 W so no effort straddles it; normalized power skips the
    stop so it doesn't dilute the average."""
    curve = metrics.mean_maximal_power(metrics.resample_1hz(time_s, power, pauses="zero"))
    normalized = metrics.normalized_power(metrics.resample_1hz(time_s, power, pauses="skip"))
    return curve, normalized


async def apply_power_metrics(
    db: AsyncSession, activity: Activity, time_s: Sequence[float], power: Sequence[float | None]
) -> None:
    """(Re)computes the power curve, normalized power and TSS of an activity
    already added to the session. Doesn't commit."""
    curve, normalized = await asyncio.to_thread(compute_power_metrics, time_s, power)
    activity.normalized_power_w = normalized
    zone = await athlete_timezone(db, await db.get(Athlete, activity.athlete_id))
    activity.tss = _tss(activity, _ftp_on(await _metric_rows(db, activity.athlete_id), local_day(activity.start_time, zone)))

    await db.flush()  # the activity row must exist before curve rows point at it
    await db.execute(delete(ActivityPowerCurve).where(ActivityPowerCurve.activity_id == activity.id))
    db.add_all(
        ActivityPowerCurve(activity_id=activity.id, duration_s=duration, power_w=watts) for duration, watts in curve.items()
    )


async def rebuild_power_metrics(db: AsyncSession, activity: Activity) -> bool:
    """Recomputes from the stored stream; False when there's no power in it."""
    stream = await db.get(ActivityStream, activity.id)
    if stream is None or stream.power_w is None:
        return False
    await apply_power_metrics(
        db, activity, streams.unpack("time_s", stream.time_s), streams.unpack("power_w", stream.power_w)
    )
    return True


async def refresh_tss(db: AsyncSession, athlete: Athlete) -> None:
    """Re-derives TSS for the athlete's power activities from the stored
    normalized power, after their FTP history changed. Doesn't commit."""
    rows = await _metric_rows(db, athlete.id)
    zone = await athlete_timezone(db, athlete)
    powered = await db.scalars(
        select(Activity).where(Activity.athlete_id == athlete.id, Activity.normalized_power_w.is_not(None))
    )
    for activity in powered:
        activity.tss = _tss(activity, _ftp_on(rows, local_day(activity.start_time, zone)))


# --- reading ---------------------------------------------------------------


def _session_seconds(event: TrainingEvent) -> float | None:
    if event.start_timestamp and event.end_timestamp:
        seconds = (event.end_timestamp - event.start_timestamp).total_seconds()
        if 0 < seconds <= _MAX_SESSION_S:
            return seconds
    return None


async def training_load(
    db: AsyncSession, athlete: Athlete, viewer: User, *, through: date, days: int
) -> TrainingLoadRead:
    """Daily load, fitness, fatigue and form for the last `days` days.

    A day's load is, per activity, its power-based TSS, else duration x RPE,
    else nothing; plus duration x RPE for each sqorz session the athlete rated
    — unless a recording of that session already counted.
    The curves are computed from the first day with load, so the window shows
    the state those days really had."""
    zone = await athlete_timezone(db, athlete)
    daily: dict[date, float] = {}
    unrated_by_day: list[date] = []
    sessions_with_load: set[uuid.UUID] = set()

    for activity in await db.scalars(select(Activity).where(*visible_conditions(athlete, viewer))):
        day = local_day(activity.start_time, zone)
        if activity.tss is not None:
            load = activity.tss
        elif activity.rpe is not None:
            load = metrics.srpe_training_stress(activity.rpe, activity.moving_s or activity.elapsed_s)
        else:
            unrated_by_day.append(day)
            continue
        daily[day] = daily.get(day, 0.0) + load
        if activity.training_event_id is not None:
            sessions_with_load.add(activity.training_event_id)

    rated_sessions = await db.scalars(
        select(TrainingEvent).where(TrainingEvent.athlete_id == athlete.id, TrainingEvent.rpe.is_not(None))
    )
    for event in rated_sessions:
        if event.id in sessions_with_load:
            continue  # the recording of this session already carries its load
        seconds = _session_seconds(event)
        if seconds is not None:
            daily[event.event_date] = daily.get(event.event_date, 0.0) + metrics.srpe_training_stress(event.rpe, seconds)

    first_shown = through - timedelta(days=days - 1)
    series = [d for d in metrics.training_load(daily, through) if d.day >= first_shown]
    return TrainingLoadRead(
        days=[TrainingLoadDay(day=d.day, tss=d.tss, ctl=d.ctl, atl=d.atl, tsb=d.tsb) for d in series],
        unrated_activities=sum(1 for day in unrated_by_day if first_shown <= day <= through),
    )


async def best_power_curve(
    db: AsyncSession, athlete: Athlete, viewer: User, *, start: datetime | None, end: datetime | None
) -> list[PowerCurvePoint]:
    """The athlete's best power at each standard duration over a date range,
    with the activity that set it."""
    query = (
        select(ActivityPowerCurve.duration_s, ActivityPowerCurve.power_w, Activity.id, Activity.start_time)
        .join(Activity, Activity.id == ActivityPowerCurve.activity_id)
        .where(*visible_conditions(athlete, viewer))
    )
    if start is not None:
        query = query.where(Activity.start_time >= start)
    if end is not None:
        query = query.where(Activity.start_time < end)
    best: dict[int, PowerCurvePoint] = {}
    for duration_s, power_w, activity_id, start_time in await db.execute(query):
        if duration_s not in best or power_w > best[duration_s].power_w:
            best[duration_s] = PowerCurvePoint(
                duration_s=duration_s, power_w=power_w, activity_id=activity_id, start_time=start_time
            )
    return [best[duration] for duration in sorted(best)]


async def analyze_activity(db: AsyncSession, athlete: Athlete, activity: Activity) -> ActivityAnalysis:
    """Zones, intensity and per-kilogram figures of one activity, from its
    stored samples and the athlete's FTP / weight / max HR on that day."""
    day = local_day(activity.start_time, await athlete_timezone(db, athlete))
    rows = await _metric_rows(db, athlete.id)
    values = metrics_as_of(rows, day)
    ftp = _ftp_on(rows, day)
    weight = float(values["weight_kg"].value) if values["weight_kg"] else None
    max_hr = int(values["max_hr"].value) if values["max_hr"] else None

    stream = await db.get(ActivityStream, activity.id)
    power_zones = hr_zones = None
    work_kj = None
    if stream is not None:
        time_s = streams.unpack("time_s", stream.time_s)
        if stream.power_w is not None:
            series = metrics.resample_1hz(time_s, streams.unpack("power_w", stream.power_w), pauses="skip")
            work_kj = sum(series) / 1000
            if ftp:
                limits = metrics.power_zone_limits(ftp)
                power_zones = ZoneDistribution(limits=limits, seconds=metrics.time_in_zones(series, limits))
        if stream.heart_rate is not None and max_hr:
            beats = metrics.resample_1hz(time_s, streams.unpack("heart_rate", stream.heart_rate), pauses="skip")
            limits = metrics.hr_zone_limits(max_hr)
            hr_zones = ZoneDistribution(limits=limits, seconds=metrics.time_in_zones(beats, limits))

    normalized, average = activity.normalized_power_w, activity.avg_power_w
    curve = await db.scalars(
        select(ActivityPowerCurve).where(ActivityPowerCurve.activity_id == activity.id).order_by(ActivityPowerCurve.duration_s)
    )
    return ActivityAnalysis(
        ftp_w=ftp,
        weight_kg=weight,
        max_hr=max_hr,
        intensity_factor=metrics.intensity_factor(normalized, ftp) if normalized and ftp else None,
        variability_index=normalized / average if normalized and average else None,
        avg_power_w_per_kg=average / weight if average and weight else None,
        normalized_power_w_per_kg=normalized / weight if normalized and weight else None,
        work_kj=work_kj,
        power_zones=power_zones,
        hr_zones=hr_zones,
        power_curve=[CurvePoint(duration_s=c.duration_s, power_w=c.power_w) for c in curve],
    )

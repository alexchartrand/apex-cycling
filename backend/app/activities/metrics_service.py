"""Persists power metrics and answers the load / power-curve questions.

The arithmetic lives in `app/analysis/metrics.py`; this module is the part
that knows about activities, FTP history, sqorz sessions and time zones.
"""

import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities import streams
from app.activities.kinds import CYCLING_TYPE_VALUES, ActivityType
from app.activities.models import Activity, ActivityPowerCurve, ActivitySource, ActivityStream
from app.activities.schemas import (
    ActivityAnalysis,
    CriticalPowerRead,
    CurvePoint,
    FtpSuggestion,
    PowerProfile,
    PowerCurvePoint,
    TrainingLoadDay,
    TrainingLoadRead,
    WeeklyLoad,
    WeeklyTypeLoad,
    ZoneDistribution,
)
from app.analysis import critical_power, metrics
from app.athletes.models import Athlete, AthleteMetric
from app.athletes.service import DatedValue, metrics_as_of, metrics_at
from app.auth.models import User
from app.clubs.models import Club
from app.training.models import TrainingEvent

# Load older than this before the first day shown is left out: CTL fades with a
# 42-day time constant, so six of them (252 days) leave under 0.25 % of it.
_LOAD_HORIZON_DAYS = 6 * metrics.CTL_DAYS

# A sqorz session window longer than this is a whole-day booking, not training time.
_MAX_SESSION_S = 6 * 3600


async def athlete_timezone(db: AsyncSession, athlete: Athlete) -> ZoneInfo:
    """The club's zone: an evening ride must land on the day it was ridden, not
    on tomorrow's UTC date. With several clubs it is the one joined first; athletes
    outside a club fall back to UTC."""
    club_ids = athlete.club_ids
    name = await db.scalar(select(Club.timezone).where(Club.id == club_ids[0])) if club_ids else None
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


def _metric_on(metric_rows: Sequence[AthleteMetric], day: date, field: str) -> float | None:
    """The `field` value in force on `day`; before the first one was entered,
    that first one (rides older than the athlete's records still deserve a TSS
    and zones)."""
    current: DatedValue | None = metrics_as_of(list(metric_rows), day)[field]
    if current is None:
        entered = [row for row in metric_rows if getattr(row, field) is not None]
        if entered:
            return float(getattr(min(entered, key=lambda row: row.effective_date), field))
        return None
    return float(current.value)


def _ftp_on(metric_rows: Sequence[AthleteMetric], day: date) -> float | None:
    return _metric_on(metric_rows, day, "ftp_w")


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


@dataclass(frozen=True)
class _LoadEntry:
    """One piece of training on a local day: its kind, the time it took, and
    its load (None when there is nothing to score it by)."""

    day: date
    activity_type: str
    seconds: float
    load: float | None
    # An activity could be given an RPE; a sqorz session is rated on its page.
    is_activity: bool = False


async def _load_entries(
    db: AsyncSession, athlete: Athlete, viewer: User, zone: ZoneInfo, *, since_day: date
) -> list[_LoadEntry]:
    """Every activity and sqorz session from `since_day` on.

    An activity counts its power-based TSS, else duration x RPE, else nothing;
    a sqorz session (track cycling) counts duration x RPE when rated — unless a
    recording of it already carries load — and its time unless a recording of
    it already counts that time."""
    entries: list[_LoadEntry] = []
    sessions_with_load: set[uuid.UUID] = set()
    sessions_recorded: set[uuid.UUID] = set()

    # A day of slack on the instant: the cut is on the local day, checked below.
    since = datetime.combine(since_day - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    for activity in await db.scalars(
        select(Activity).where(*visible_conditions(athlete, viewer), Activity.start_time >= since)
    ):
        day = local_day(activity.start_time, zone)
        if day < since_day:
            continue
        seconds = activity.moving_s or activity.elapsed_s
        if activity.tss is not None:
            load = activity.tss
        elif activity.rpe is not None:
            load = metrics.srpe_training_stress(activity.rpe, seconds)
        else:
            load = None
        entries.append(_LoadEntry(day, activity.activity_type, seconds, load, is_activity=True))
        if activity.training_event_id is not None:
            sessions_recorded.add(activity.training_event_id)
            if load is not None:
                sessions_with_load.add(activity.training_event_id)

    sessions = await db.scalars(
        select(TrainingEvent).where(TrainingEvent.athlete_id == athlete.id, TrainingEvent.event_date >= since_day)
    )
    for event in sessions:
        seconds = _session_seconds(event)
        if seconds is None:
            continue
        load = None
        if event.rpe is not None and event.id not in sessions_with_load:
            load = metrics.srpe_training_stress(event.rpe, seconds)
        counted_s = 0.0 if event.id in sessions_recorded else seconds
        if load is not None or counted_s:
            entries.append(_LoadEntry(event.event_date, ActivityType.TRACK_CYCLING.value, counted_s, load))
    return entries


async def training_load(
    db: AsyncSession, athlete: Athlete, viewer: User, *, through: date, days: int
) -> TrainingLoadRead:
    """Daily load, fitness, fatigue and form for the last `days` days (load per
    `_load_entries`). The curves are computed from the first day with load
    inside the horizon (`_LOAD_HORIZON_DAYS` before the window), so the window
    shows the state those days really had, and a long history isn't read for a
    short window."""
    zone = await athlete_timezone(db, athlete)
    first_shown = through - timedelta(days=days - 1)
    horizon = first_shown - timedelta(days=_LOAD_HORIZON_DAYS)
    entries = await _load_entries(db, athlete, viewer, zone, since_day=horizon)
    daily: dict[date, float] = {}
    for entry in entries:
        if entry.load is not None:
            daily[entry.day] = daily.get(entry.day, 0.0) + entry.load

    unrated = sum(
        1 for entry in entries if entry.is_activity and entry.load is None and first_shown <= entry.day <= through
    )
    series = [d for d in metrics.training_load(daily, through) if d.day >= first_shown]
    return TrainingLoadRead(
        days=[TrainingLoadDay(day=d.day, tss=d.tss, ctl=d.ctl, atl=d.atl, tsb=d.tsb) for d in series],
        unrated_activities=unrated,
    )


async def weekly_load_by_type(
    db: AsyncSession, athlete: Athlete, viewer: User, *, through: date, weeks: int
) -> list[WeeklyLoad]:
    """Per Monday-start week (oldest first, the last one holding `through`),
    the time and load of each kind of training."""
    zone = await athlete_timezone(db, athlete)
    last_monday = through - timedelta(days=through.weekday())
    first_monday = last_monday - timedelta(weeks=weeks - 1)
    totals: dict[date, dict[str, list[float]]] = {first_monday + timedelta(weeks=i): {} for i in range(weeks)}
    for entry in await _load_entries(db, athlete, viewer, zone, since_day=first_monday):
        if entry.day > through:
            continue
        week = totals[entry.day - timedelta(days=entry.day.weekday())]
        seconds, load = week.setdefault(entry.activity_type, [0.0, 0.0])
        week[entry.activity_type] = [seconds + entry.seconds, load + (entry.load or 0.0)]
    return [
        WeeklyLoad(
            week_start=monday,
            types=[
                WeeklyTypeLoad(activity_type=kind, seconds=round(seconds), tss=round(load, 1))
                for kind, (seconds, load) in sorted(by_type.items())
            ],
        )
        for monday, by_type in totals.items()
    ]


async def best_power_curve(
    db: AsyncSession, athlete: Athlete, viewer: User, *, start: datetime | None, end: datetime | None
) -> list[PowerCurvePoint]:
    """The athlete's best power at each standard duration over a date range,
    with the activity that set it."""
    query = (
        select(ActivityPowerCurve.duration_s, ActivityPowerCurve.power_w, Activity.id, Activity.start_time)
        .join(Activity, Activity.id == ActivityPowerCurve.activity_id)
        # Only rides: a gym session's (or, later, a run's) power isn't cycling power.
        .where(*visible_conditions(athlete, viewer), Activity.activity_type.in_(CYCLING_TYPE_VALUES))
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


async def power_profile(db: AsyncSession, athlete: Athlete, viewer: User, *, days: int) -> PowerProfile:
    """Critical power / W′ and an FTP suggestion from the best power of the last
    `days` days. The FTP suggestion is left out when it is within a couple of
    percent of the FTP already in force."""
    now = datetime.now(timezone.utc)
    curve = await best_power_curve(db, athlete, viewer, start=now - timedelta(days=days), end=None)
    pairs = [(point.duration_s, point.power_w) for point in curve]

    fit = critical_power.fit_critical_power(pairs)
    today = local_day(now, await athlete_timezone(db, athlete))
    current = (await metrics_at(db, athlete.id, today))["ftp_w"]
    current_w = float(current.value) if current is not None else None

    suggestion = None
    suggested = critical_power.suggest_ftp(pairs)
    if suggested is not None and critical_power.worth_suggesting(suggested[0], current_w):
        source = next(point for point in curve if point.duration_s == suggested[1])
        suggestion = FtpSuggestion(
            ftp_w=suggested[0],
            source_duration_s=suggested[1],
            source_activity_id=source.activity_id,
            source_power_w=source.power_w,
        )
    return PowerProfile(
        days=days,
        critical_power=CriticalPowerRead(
            cp_w=fit.cp_w, w_prime_j=fit.w_prime_j, r_squared=fit.r_squared, points=fit.points
        )
        if fit
        else None,
        ftp_current_w=current_w,
        ftp_suggestion=suggestion,
    )


async def analyze_activity(db: AsyncSession, athlete: Athlete, activity: Activity) -> ActivityAnalysis:
    """Zones, intensity and per-kilogram figures of one activity, from its
    stored samples and the athlete's FTP / weight / max HR on that day."""
    day = local_day(activity.start_time, await athlete_timezone(db, athlete))
    rows = await _metric_rows(db, athlete.id)
    values = metrics_as_of(rows, day)
    ftp = _ftp_on(rows, day)
    weight = float(values["weight_kg"].value) if values["weight_kg"] else None
    max_hr_value = _metric_on(rows, day, "max_hr")
    max_hr = int(max_hr_value) if max_hr_value else None

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

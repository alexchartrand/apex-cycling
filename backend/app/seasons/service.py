"""Seasons, the race calendar and the calendar-feed link. Everything about a
season (its end, its bests) and a race (days to go, the taper) is worked out on
every read, so it follows lap edits and new results. Functions return None when
the row isn't this athlete's; those that change something commit.
"""

import hashlib
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import athlete_timezone, local_day
from app.athletes.models import Athlete
from app.auth.models import User
from app.core.config import get_settings
from app.goals.models import Goal
from app.planning.models import PlannedSession, PlanStatus
from app.seasons import planning
from app.seasons.ics import CalendarEntry, build_calendar
from app.seasons.models import CalendarFeed, Competition, Season
from app.seasons.schemas import (
    CalendarFeedStatus,
    CompetitionGoal,
    CompetitionRead,
    CompetitionUpdate,
    CompetitionWrite,
    SeasonBest,
    SeasonRead,
    SeasonSummary,
    SeasonUpdate,
    SeasonWrite,
)
from app.training.efforts import StartType
from app.training.models import ManualResult, Track, TrainingEvent
from app.training.records_service import _EVENT_ORDER, _START_ORDER, _place_key, load_session_inputs, results_of

# The feed looks this far back and ahead.
FEED_DAYS_BACK = 60
FEED_DAYS_AHEAD = 400


class DuplicateSeason(Exception):
    """The athlete already has a season starting that day."""


class UnknownGoal(Exception):
    """The goal isn't one of this athlete's."""


async def _today(db: AsyncSession, athlete: Athlete) -> date:
    return local_day(datetime.now(timezone.utc), await athlete_timezone(db, athlete))


# --- seasons -----------------------------------------------------------------------------


def _season_reads(rows: list[Season], today: date) -> list[SeasonRead]:
    """Newest first. A season ends the day before the next one starts."""
    ordered = sorted(rows, key=lambda row: row.start_date)
    reads = []
    for index, row in enumerate(ordered):
        end = ordered[index + 1].start_date - timedelta(days=1) if index + 1 < len(ordered) else None
        reads.append(
            SeasonRead(
                id=row.id,
                name=row.name,
                start_date=row.start_date,
                end_date=end,
                is_current=row.start_date <= today and (end is None or today <= end),
            )
        )
    return list(reversed(reads))


async def _season_rows(db: AsyncSession, athlete_id: uuid.UUID) -> list[Season]:
    return list(await db.scalars(select(Season).where(Season.athlete_id == athlete_id)))


async def list_seasons(db: AsyncSession, athlete: Athlete) -> list[SeasonRead]:
    return _season_reads(await _season_rows(db, athlete.id), await _today(db, athlete))


async def _read_season(db: AsyncSession, athlete: Athlete, season_id: uuid.UUID) -> SeasonRead | None:
    return next((s for s in await list_seasons(db, athlete) if s.id == season_id), None)


async def create_season(db: AsyncSession, athlete: Athlete, payload: SeasonWrite) -> SeasonRead:
    season = Season(athlete_id=athlete.id, name=payload.name, start_date=payload.start_date)
    db.add(season)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DuplicateSeason from None
    return await _read_season(db, athlete, season.id)


async def update_season(db: AsyncSession, athlete: Athlete, season_id: uuid.UUID, payload: SeasonUpdate) -> SeasonRead | None:
    season = await db.get(Season, season_id)
    if season is None or season.athlete_id != athlete.id:
        return None
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(season, field_name, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DuplicateSeason from None
    return await _read_season(db, athlete, season_id)


async def delete_season(db: AsyncSession, athlete_id: uuid.UUID, season_id: uuid.UUID) -> bool:
    season = await db.get(Season, season_id)
    if season is None or season.athlete_id != athlete_id:
        return False
    await db.delete(season)
    await db.commit()
    return True


class _Entry:
    """One result of the athlete, from a sqorz session or entered by hand."""

    __slots__ = ("key", "place", "track_id", "event_key", "start_type", "time_ms", "day", "source", "external_event_id")

    def __init__(self, track_id, venue, place, event_key, start_type, time_ms, day, source, external_event_id=None):
        self.key = (_place_key(track_id, venue if track_id is None else None), event_key, start_type)
        self.place, self.track_id = place, track_id
        self.event_key, self.start_type, self.time_ms, self.day = event_key, start_type, time_ms, day
        self.source, self.external_event_id = source, external_event_id


async def _all_results(db: AsyncSession, athlete_id: uuid.UUID) -> list[_Entry]:
    results = results_of(await load_session_inputs(db, athlete_id))
    manual = list(await db.scalars(select(ManualResult).where(ManualResult.athlete_id == athlete_id)))
    track_ids = {r.track_id for r in results} | {m.track_id for m in manual if m.track_id is not None}
    tracks = (
        {track.id: track.name for track in await db.scalars(select(Track).where(Track.id.in_(track_ids)))} if track_ids else {}
    )
    external_ids = dict(
        (
            await db.execute(
                select(TrainingEvent.id, TrainingEvent.external_event_id).where(TrainingEvent.athlete_id == athlete_id)
            )
        ).all()
    )
    entries = [
        _Entry(
            result.track_id, None, tracks.get(result.track_id, ""), result.event_key, result.start_type,
            result.time_ms, result.event_date, "sqorz", external_ids.get(result.training_event_id),
        )
        for result in results
    ]  # fmt: skip
    for row in manual:
        entries.append(
            _Entry(
                row.track_id, row.venue, tracks.get(row.track_id) or row.venue or "", row.event_key,
                StartType(row.start_type), row.time_ms, row.achieved_on, "manual",
            )  # fmt: skip
        )
    return entries


def season_bests(entries: list[_Entry], start: date, end: date | None) -> list[SeasonBest]:
    """The best of each place, event and start inside [start, end], against the
    best before `start`."""
    in_season: dict[tuple, _Entry] = {}
    before: dict[tuple, int] = {}
    for entry in entries:
        if entry.day < start:
            if entry.key not in before or entry.time_ms < before[entry.key]:
                before[entry.key] = entry.time_ms
        elif end is None or entry.day <= end:
            current = in_season.get(entry.key)
            if current is None or (entry.time_ms, entry.day) < (current.time_ms, current.day):
                in_season[entry.key] = entry
    bests = [
        SeasonBest(
            place=entry.place,
            track_id=entry.track_id,
            event_key=entry.event_key,
            start_type=entry.start_type,
            time_ms=entry.time_ms,
            achieved_on=entry.day,
            source=entry.source,
            external_event_id=entry.external_event_id,
            previous_best_ms=before.get(key),
            improved=key in before and entry.time_ms < before[key],
        )
        for key, entry in in_season.items()
    ]
    bests.sort(key=lambda b: (b.place.casefold(), _EVENT_ORDER.get(b.event_key, 99), _START_ORDER[b.start_type]))
    return bests


async def season_summary(db: AsyncSession, athlete: Athlete, season_id: uuid.UUID) -> SeasonSummary | None:
    season = await _read_season(db, athlete, season_id)
    if season is None:
        return None
    window = [TrainingEvent.athlete_id == athlete.id, TrainingEvent.event_date >= season.start_date]
    if season.end_date is not None:
        window.append(TrainingEvent.event_date <= season.end_date)
    sessions = await db.scalar(select(func.count()).select_from(TrainingEvent).where(*window))
    races = await db.scalar(select(func.count()).select_from(TrainingEvent).where(*window, TrainingEvent.is_race.is_(True)))
    return SeasonSummary(
        season=season,
        sessions=sessions or 0,
        races=races or 0,
        bests=season_bests(await _all_results(db, athlete.id), season.start_date, season.end_date),
    )


# --- competitions ---------------------------------------------------------------------------


async def _check_goal(db: AsyncSession, athlete_id: uuid.UUID, goal_id: uuid.UUID | None) -> None:
    if goal_id is None:
        return
    goal = await db.get(Goal, goal_id)
    if goal is None or goal.athlete_id != athlete_id:
        raise UnknownGoal


async def _competition_reads(
    db: AsyncSession, athlete: Athlete, rows: list[Competition], today: date
) -> list[CompetitionRead]:
    goal_ids = {row.goal_id for row in rows if row.goal_id}
    goals = {goal.id: goal for goal in await db.scalars(select(Goal).where(Goal.id.in_(goal_ids)))} if goal_ids else {}
    race_sessions: dict[date, str] = {}
    days = {row.competition_date for row in rows}
    if days:
        for day, external_id in await db.execute(
            select(TrainingEvent.event_date, TrainingEvent.external_event_id)
            .where(
                TrainingEvent.athlete_id == athlete.id,
                TrainingEvent.is_race.is_(True),
                TrainingEvent.event_date.in_(days),
            )
            .order_by(TrainingEvent.external_event_id.desc())
        ):
            race_sessions[day] = external_id

    reads = []
    for row in rows:
        count = planning.countdown(row.competition_date, row.priority, today)
        goal = goals.get(row.goal_id)
        reads.append(
            CompetitionRead(
                id=row.id,
                name=row.name,
                competition_date=row.competition_date,
                priority=row.priority,
                location=row.location,
                notes=row.notes,
                goal=CompetitionGoal(
                    id=goal.id,
                    event_key=goal.event_key,
                    start_type=StartType(goal.start_type),
                    target_time_ms=goal.target_time_ms,
                )
                if goal
                else None,
                days_until=count.days_until,
                taper_starts_on=count.taper_starts_on,
                days_to_taper=count.days_to_taper,
                phase=count.phase,
                race_session_id=race_sessions.get(row.competition_date),
            )
        )
    return reads


async def list_competitions(db: AsyncSession, athlete: Athlete) -> list[CompetitionRead]:
    """Coming races soonest first, then the past ones, most recent first."""
    today = await _today(db, athlete)
    rows = list(await db.scalars(select(Competition).where(Competition.athlete_id == athlete.id)))
    upcoming = sorted((r for r in rows if r.competition_date >= today), key=lambda r: r.competition_date)
    past = sorted((r for r in rows if r.competition_date < today), key=lambda r: r.competition_date, reverse=True)
    return await _competition_reads(db, athlete, upcoming + past, today)


async def _one_competition(db: AsyncSession, athlete: Athlete, competition: Competition) -> CompetitionRead:
    return (await _competition_reads(db, athlete, [competition], await _today(db, athlete)))[0]


async def create_competition(db: AsyncSession, athlete: Athlete, payload: CompetitionWrite) -> CompetitionRead:
    await _check_goal(db, athlete.id, payload.goal_id)
    competition = Competition(athlete_id=athlete.id, **payload.model_dump())
    db.add(competition)
    await db.commit()
    return await _one_competition(db, athlete, competition)


async def update_competition(
    db: AsyncSession, athlete: Athlete, competition_id: uuid.UUID, payload: CompetitionUpdate
) -> CompetitionRead | None:
    competition = await db.get(Competition, competition_id)
    if competition is None or competition.athlete_id != athlete.id:
        return None
    changes = payload.model_dump(exclude_unset=True)
    await _check_goal(db, athlete.id, changes.get("goal_id"))
    for field_name, value in changes.items():
        setattr(competition, field_name, value)
    await db.commit()
    return await _one_competition(db, athlete, competition)


async def delete_competition(db: AsyncSession, athlete_id: uuid.UUID, competition_id: uuid.UUID) -> bool:
    competition = await db.get(Competition, competition_id)
    if competition is None or competition.athlete_id != athlete_id:
        return False
    await db.delete(competition)
    await db.commit()
    return True


# --- calendar feed --------------------------------------------------------------------------


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def feed_status(db: AsyncSession, athlete_id: uuid.UUID) -> CalendarFeedStatus:
    return CalendarFeedStatus(enabled=await db.scalar(select(CalendarFeed.id).where(CalendarFeed.athlete_id == athlete_id)) is not None)


async def enable_feed(db: AsyncSession, athlete: Athlete) -> CalendarFeedStatus:
    """Makes (or replaces) the athlete's secret link. The URL is only in this answer."""
    athlete_id = athlete.id  # a rollback below expires `athlete`
    token = secrets.token_urlsafe(32)
    feed = await db.scalar(select(CalendarFeed).where(CalendarFeed.athlete_id == athlete_id))
    if feed is None:
        db.add(CalendarFeed(athlete_id=athlete_id, token_hash=_hash(token)))
    else:
        feed.token_hash = _hash(token)
    try:
        await db.commit()
    except IntegrityError:
        # Another request made the row first (a double click): take it over with our token.
        await db.rollback()
        feed = await db.scalar(select(CalendarFeed).where(CalendarFeed.athlete_id == athlete_id))
        feed.token_hash = _hash(token)
        await db.commit()
    base = get_settings().app_base_url.rstrip("/")
    return CalendarFeedStatus(enabled=True, url=f"{base}/api/calendar/{token}.ics")


async def disable_feed(db: AsyncSession, athlete_id: uuid.UUID) -> None:
    await db.execute(delete(CalendarFeed).where(CalendarFeed.athlete_id == athlete_id))
    await db.commit()


_WORDS = {
    "en": {"standing": "standing start", "flying": "flying start", "race": "Race", "taper": "Taper starts", "target": "target"},
    "fr": {"standing": "départ arrêté", "flying": "départ lancé", "race": "Compétition", "taper": "Début de l'affûtage", "target": "objectif"},
}  # fmt: skip


def _time(ms: int) -> str:
    minutes, rest = divmod(ms, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{minutes}:{seconds:02d}.{millis:03d}" if minutes else f"{seconds}.{millis:03d}"


def _target_lines(targets: list[dict], words: dict[str, str]) -> list[str]:
    lines = []
    for target in targets:
        parts = [f"{target['label']} ×{target.get('reps', 1)}"]
        if target.get("event_key"):
            parts.append(" ".join(filter(None, [target["event_key"], words.get(target.get("start_type") or "", "")])))
        if target.get("target_time_ms"):
            parts.append(_time(target["target_time_ms"]))
        lines.append(" · ".join(parts))
    return lines


async def calendar_for_token(db: AsyncSession, token: str) -> str | None:
    """The .ics text for the secret link, or None when the link isn't (or is no longer) valid."""
    feed = await db.scalar(select(CalendarFeed).where(CalendarFeed.token_hash == _hash(token)))
    if feed is None:
        return None
    athlete = await db.get(Athlete, feed.athlete_id)
    user = await db.get(User, athlete.user_id) if athlete.user_id else None
    words = _WORDS.get((user.locale if user and user.locale else "fr")[:2], _WORDS["fr"])
    now = datetime.now(timezone.utc)
    today = local_day(now, await athlete_timezone(db, athlete))
    start, end = today - timedelta(days=FEED_DAYS_BACK), today + timedelta(days=FEED_DAYS_AHEAD)

    entries: list[CalendarEntry] = []
    plans = await db.scalars(
        select(PlannedSession).where(
            PlannedSession.athlete_id == athlete.id,
            PlannedSession.planned_date >= start,
            PlannedSession.planned_date <= end,
            PlannedSession.status != PlanStatus.SKIPPED.value,
        )
    )
    for plan in plans:
        description = "\n".join(filter(None, [plan.description, *_target_lines(plan.targets or [], words)]))
        entries.append(
            CalendarEntry(
                uid=f"plan-{plan.id}@apex-cycling",
                day=plan.planned_date,
                summary=("✓ " if plan.status == PlanStatus.DONE.value else "") + plan.title,
                description=description or None,
            )
        )
    competitions = list(
        await db.scalars(
            select(Competition).where(
                Competition.athlete_id == athlete.id,
                Competition.competition_date >= start,
                Competition.competition_date <= end,
            )
        )
    )
    goals = {g.id: g for g in await db.scalars(select(Goal).where(Goal.athlete_id == athlete.id))}
    for race in competitions:
        goal = goals.get(race.goal_id)
        goal_line = f"{words['target']}: {goal.event_key} {_time(goal.target_time_ms)}" if goal else None
        entries.append(
            CalendarEntry(
                uid=f"race-{race.id}@apex-cycling",
                day=race.competition_date,
                summary=f"🏁 {race.name} ({race.priority})",
                description="\n".join(filter(None, [race.notes, goal_line])) or None,
                location=race.location,
            )
        )
        taper_start = planning.countdown(race.competition_date, race.priority, today).taper_starts_on
        if taper_start is not None and taper_start >= start:
            entries.append(
                CalendarEntry(uid=f"taper-{race.id}@apex-cycling", day=taper_start, summary=f"{words['taper']} – {race.name}")
            )
    entries.sort(key=lambda e: (e.day, e.uid))
    return build_calendar(f"ApexCycling – {athlete.display_name}", entries, now)

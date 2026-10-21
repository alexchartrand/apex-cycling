"""The club leaderboard: the best time per athlete on one track for one event,
among athletes who opted in. Opting in is per club (`Athlete.leaderboard_club_id`
must still be the athlete's `club_id`), so it follows the athlete's consent and
ends when they leave. Times come from `personal_records` (computed from sqorz
laps) and from manual results that name the track; Strava activities never feed
either, which keeps them out of every shared view.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.categories import age_category
from app.athletes.models import Athlete
from app.clubs.schemas import Leaderboard, LeaderboardEntry
from app.training.efforts import StartType
from app.training.models import ManualResult, PersonalRecord, Track


async def opted_in_athletes(db: AsyncSession, club_id: uuid.UUID) -> list[Athlete]:
    return list(
        await db.scalars(
            select(Athlete).where(Athlete.club_id == club_id, Athlete.leaderboard_club_id == club_id)
        )
    )


async def _best_times(
    db: AsyncSession, athlete_ids: list[uuid.UUID], track_id: uuid.UUID, event_key: str, start_type: StartType
) -> dict[uuid.UUID, tuple[int, date, str]]:
    """athlete id -> (time, day, source), the fastest of records and manual results."""
    best: dict[uuid.UUID, tuple[int, date, str]] = {}

    def offer(athlete_id: uuid.UUID, time_ms: int, day: date, source: str) -> None:
        current = best.get(athlete_id)
        if current is None or (time_ms, day) < (current[0], current[1]):
            best[athlete_id] = (time_ms, day, source)

    if not athlete_ids:
        return best
    for record in await db.scalars(
        select(PersonalRecord).where(
            PersonalRecord.athlete_id.in_(athlete_ids),
            PersonalRecord.track_id == track_id,
            PersonalRecord.event_key == event_key,
            PersonalRecord.start_type == start_type.value,
        )
    ):
        offer(record.athlete_id, record.time_ms, record.achieved_on, "sqorz")
    for result in await db.scalars(
        select(ManualResult).where(
            ManualResult.athlete_id.in_(athlete_ids),
            ManualResult.track_id == track_id,
            ManualResult.event_key == event_key,
            ManualResult.start_type == start_type.value,
        )
    ):
        offer(result.athlete_id, result.time_ms, result.achieved_on, "manual")
    return best


async def build_leaderboard(
    db: AsyncSession,
    club_id: uuid.UUID,
    track: Track,
    event_key: str,
    start_type: StartType,
    *,
    viewer_athlete_id: uuid.UUID | None,
    sex: str | None = None,
    category: str | None = None,
    today: date | None = None,
) -> Leaderboard:
    athletes = await opted_in_athletes(db, club_id)
    times = await _best_times(db, [a.id for a in athletes], track.id, event_key, start_type)

    rows = []
    for athlete in athletes:
        if athlete.id not in times:
            continue
        found = age_category(athlete.birthdate, today)
        rows.append((athlete, times[athlete.id], found.code if found else None))
    categories = sorted({code for _, _, code in rows if code}, key=_category_order)

    kept = [
        (athlete, best, code)
        for athlete, best, code in rows
        if (sex is None or athlete.sex == sex) and (category is None or code == category)
    ]
    kept.sort(key=lambda row: (row[1][0], row[1][1], row[0].display_name.casefold()))

    entries: list[LeaderboardEntry] = []
    for index, (athlete, (time_ms, day, source), code) in enumerate(kept):
        # Equal times share a rank ("1, 1, 3").
        rank = entries[-1].rank if entries and entries[-1].time_ms == time_ms else index + 1
        entries.append(
            LeaderboardEntry(
                rank=rank,
                display_name=athlete.display_name,
                time_ms=time_ms,
                achieved_on=day,
                sex=athlete.sex,
                category=code,
                source=source,
                is_me=athlete.id == viewer_athlete_id,
            )
        )
    return Leaderboard(
        event_key=event_key,
        start_type=start_type,
        track_id=track.id,
        track_name=track.name,
        participants=len(athletes),
        categories=categories,
        entries=entries,
    )


_CATEGORY_ORDER = ("U11", "U13", "U15", "U17", "U19", "U23", "ELITE")


def _category_order(code: str) -> tuple[int, int]:
    """Youth to elite, then masters by age."""
    if code in _CATEGORY_ORDER:
        return (0, _CATEGORY_ORDER.index(code))
    return (1, int(code[1:]))

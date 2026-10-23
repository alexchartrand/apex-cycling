"""Session insights ("PR moments"), as pure functions.

An insight is a headline about one session derived from the athlete's whole
history: a new personal record (with the round number it broke, if any), a
season best, the best Nth lap of an effort this season, the most consistent
effort this season. Nothing is stored — like the record history they are
recomputed on read, so they follow lap edits, exclusions and track-length
changes. `insights_service.py` loads the data; the decisions live here.

A season is the calendar year of the session date. A result only makes a
headline when there is something earlier to compare it with: the very first
result of an event isn't a "record" worth celebrating.
"""

import statistics
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from app.training.efforts import Effort, StartType
from app.training.records import Result

# Efforts shorter than this have too few laps for a pacing or "Nth lap" headline.
MIN_EFFORT_LAPS = 4
# Lap positions beyond this aren't tracked ("best 25th lap" is noise).
MAX_LAP_NUMBER = 20
# A comparable effort has a lap count within this factor of the one compared.
CONSISTENCY_LAP_COUNT_RATIO = 1.34


class InsightKind(str, Enum):
    PERSONAL_RECORD = "personal_record"
    SEASON_BEST = "season_best"
    BEST_NTH_LAP = "best_nth_lap"
    MOST_CONSISTENT = "most_consistent"


# Most notable first, for ordering the headlines of one session.
_KIND_ORDER = {kind: index for index, kind in enumerate(InsightKind)}


@dataclass(frozen=True)
class Insight:
    kind: InsightKind
    training_event_id: uuid.UUID
    track_id: uuid.UUID
    event_date: date
    # personal_record / season_best
    event_key: str | None = None
    start_type: StartType | None = None
    time_ms: int | None = None
    previous_ms: int | None = None  # the best before this session (season best: this season's)
    milestone_ms: int | None = None  # personal_record only: first time under this round time
    # best_nth_lap / most_consistent
    lap_number: int | None = None  # 1-based position within the effort
    lap_count: int | None = None  # laps compared (most_consistent)
    cv_pct: float | None = None  # lap-time spread, % of the mean (most_consistent)
    effort_start_type: StartType | None = None
    first_lap_id: uuid.UUID | None = None  # the performance's first lap / the effort's first lap

    @property
    def key(self) -> str:
        """Stable identity across recomputes: one headline per session, track,
        kind and what it is about. A notification is sent once per key.
        """
        subject = f"{self.event_key}:{self.start_type.value}" if self.event_key and self.start_type else ""
        if self.lap_number is not None and self.kind == InsightKind.BEST_NTH_LAP:
            subject = f"lap{self.lap_number}:{self.effort_start_type.value if self.effort_start_type else ''}"
        return f"{self.training_event_id}:{self.track_id}:{self.kind.value}:{subject}"


@dataclass(frozen=True)
class EffortFacts:
    """One detected effort with what the insights need to know about it."""

    training_event_id: uuid.UUID
    track_id: uuid.UUID
    event_date: date
    effort: Effort


def milestone_step_ms(time_ms: int) -> int:
    """Granularity of "round" times: a second below a minute, five seconds
    below five minutes, ten seconds above.
    """
    if time_ms < 60_000:
        return 1_000
    if time_ms < 300_000:
        return 5_000
    return 10_000


def broken_milestone_ms(previous_ms: int, time_ms: int) -> int | None:
    """The round time just above `time_ms` that `previous_ms` was not under
    ("first time under 20 s"), if the new time crossed one. 20.000 exactly
    isn't under 20 s.
    """
    step = milestone_step_ms(time_ms)
    candidate = (time_ms // step + 1) * step
    return candidate if previous_ms >= candidate else None


def result_insights(results: Sequence[Result]) -> list[Insight]:
    """Personal records and season bests among the sessions' best results."""
    by_key: dict[tuple[uuid.UUID, str, StartType], list[Result]] = defaultdict(list)
    for result in results:
        by_key[result.key].append(result)

    insights: list[Insight] = []
    for chronological in (sorted(group, key=lambda r: r.achieved_at) for group in by_key.values()):
        for index, result in enumerate(chronological):
            earlier = chronological[:index]
            if not earlier:
                continue
            best_before = min(r.time_ms for r in earlier)
            common = dict(
                training_event_id=result.training_event_id,
                track_id=result.track_id,
                event_date=result.event_date,
                event_key=result.event_key,
                start_type=result.start_type,
                time_ms=result.time_ms,
                first_lap_id=result.lap_id,
            )
            if result.time_ms < best_before:
                insights.append(
                    Insight(
                        InsightKind.PERSONAL_RECORD,
                        previous_ms=best_before,
                        milestone_ms=broken_milestone_ms(best_before, result.time_ms),
                        **common,
                    )
                )
                continue
            same_season = [r.time_ms for r in earlier if r.event_date.year == result.event_date.year]
            if same_season and result.time_ms < min(same_season):
                insights.append(Insight(InsightKind.SEASON_BEST, previous_ms=min(same_season), **common))
    return insights


def _lap_time_at(effort: Effort, index: int) -> int | None:
    """A lap's time when it counts: finished and not excluded."""
    if effort.laps[index].excluded:
        return None
    return effort.lap_times_ms[index]


def best_nth_lap_insights(efforts: Sequence[EffortFacts], *, skip_lap_ids: frozenset[uuid.UUID] = frozenset()) -> list[Insight]:
    """"Best 3rd lap this season": for each lap position of efforts with
    enough laps, a session's best beating every earlier same-season one on the
    track with the same kind of start. One headline per session and track —
    the one that improved most — so a long session doesn't list every lap.
    `skip_lap_ids` are laps already celebrated as a record, not repeated.
    """
    # (track, season, start type, position) -> [(session start, event id, lap time, first lap id)], per session best.
    best_in_session: dict[tuple, dict[uuid.UUID, tuple[datetime, int, uuid.UUID, date]]] = defaultdict(dict)
    for facts in efforts:
        effort = facts.effort
        if effort.completed_lap_count < MIN_EFFORT_LAPS or effort.start_type == StartType.UNKNOWN:
            continue
        for index in range(min(len(effort.laps), MAX_LAP_NUMBER)):
            time_ms = _lap_time_at(effort, index)
            if time_ms is None:
                continue
            key = (facts.track_id, facts.event_date.year, effort.start_type, index + 1)
            current = best_in_session[key].get(facts.training_event_id)
            if current is None or time_ms < current[1]:
                best_in_session[key][facts.training_event_id] = (
                    effort.laps[index].start_time,
                    time_ms,
                    effort.laps[index].lap_id,
                    facts.event_date,
                )

    candidates: dict[tuple[uuid.UUID, uuid.UUID], tuple[int, Insight]] = {}
    for (track_id, _year, start_type, position), sessions in best_in_session.items():
        chronological = sorted(sessions.items(), key=lambda item: item[1][0])
        for index, (event_id, (_when, time_ms, lap_id, event_date)) in enumerate(chronological):
            earlier = [entry[1] for _, entry in chronological[:index]]
            if not earlier or time_ms >= min(earlier) or lap_id in skip_lap_ids:
                continue
            improvement = min(earlier) - time_ms
            current = candidates.get((event_id, track_id))
            if current is None or improvement > current[0]:
                candidates[(event_id, track_id)] = (
                    improvement,
                    Insight(
                        InsightKind.BEST_NTH_LAP,
                        training_event_id=event_id,
                        track_id=track_id,
                        event_date=event_date,
                        time_ms=time_ms,
                        previous_ms=min(earlier),
                        lap_number=position,
                        effort_start_type=start_type,
                        first_lap_id=lap_id,
                    ),
                )
    return [insight for _, insight in candidates.values()]


def lap_time_cv_pct(effort: Effort) -> tuple[float, int] | None:
    """(spread of lap times as % of their mean, laps compared) for an effort,
    or None if it's too short or has a hole. A standing start's first lap is
    left out — it is slow by design, not unevenly paced.
    """
    skip_first = effort.start_type == StartType.STANDING
    times: list[int] = []
    for index in range(1 if skip_first else 0, len(effort.laps)):
        time_ms = _lap_time_at(effort, index)
        if time_ms is None:
            return None
        times.append(time_ms)
    if len(times) < MIN_EFFORT_LAPS - 1:
        return None
    return statistics.pstdev(times) / statistics.fmean(times) * 100, len(times)


def most_consistent_insights(efforts: Sequence[EffortFacts]) -> list[Insight]:
    """"Most consistent effort this season": the session's evenest-paced
    effort when it beats every comparable earlier one (same track and start
    type, similar number of laps, same season). At most one per session and
    track.
    """
    scored: list[tuple[EffortFacts, float, int]] = []
    for facts in efforts:
        if facts.effort.completed_lap_count < MIN_EFFORT_LAPS or facts.effort.start_type == StartType.UNKNOWN:
            continue
        spread = lap_time_cv_pct(facts.effort)
        if spread is not None:
            scored.append((facts, spread[0], spread[1]))
    scored.sort(key=lambda item: item[0].effort.start_time)

    def comparable(lap_count: int, other: int) -> bool:
        ratio = max(lap_count, other) / min(lap_count, other)
        return ratio <= CONSISTENCY_LAP_COUNT_RATIO

    winners: dict[tuple[uuid.UUID, uuid.UUID], tuple[EffortFacts, float, int]] = {}
    for index, (facts, cv, lap_count) in enumerate(scored):
        earlier = [
            other_cv
            for other, other_cv, other_count in scored[:index]
            if other.track_id == facts.track_id
            and other.event_date.year == facts.event_date.year
            and other.effort.start_type == facts.effort.start_type
            and other.training_event_id != facts.training_event_id
            and comparable(lap_count, other_count)
        ]
        if not earlier or cv >= min(earlier):
            continue
        slot = (facts.training_event_id, facts.track_id)
        if slot not in winners or cv < winners[slot][1]:
            winners[slot] = (facts, cv, lap_count)

    return [
        Insight(
            InsightKind.MOST_CONSISTENT,
            training_event_id=facts.training_event_id,
            track_id=facts.track_id,
            event_date=facts.event_date,
            cv_pct=round(cv, 2),
            lap_count=lap_count,
            effort_start_type=facts.effort.start_type,
            first_lap_id=facts.effort.laps[0].lap_id,
        )
        for facts, cv, lap_count in winners.values()
    ]


def derive_insights(results: Sequence[Result], efforts: Sequence[EffortFacts]) -> list[Insight]:
    """Every insight across the athlete's history, newest session first and
    the most notable kind first within a session.
    """
    from_results = result_insights(results)
    celebrated_laps = frozenset(i.first_lap_id for i in from_results if i.event_key == "lap" and i.first_lap_id)
    everything = [
        *from_results,
        *best_nth_lap_insights(efforts, skip_lap_ids=celebrated_laps),
        *most_consistent_insights(efforts),
    ]
    return sorted(
        everything,
        key=lambda i: (-i.event_date.toordinal(), str(i.training_event_id), _KIND_ORDER[i.kind], i.event_key or "", i.lap_number or 0),
    )

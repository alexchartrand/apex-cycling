import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.connections.service import create_transponder_assignment
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.training.efforts import (
    CheckpointCrossing,
    LapInput,
    StartType,
    classify_start,
    detect_efforts,
    group_continuous_laps,
    half_lap_splits,
    pursuit_line,
)

_T0 = datetime(2026, 7, 7, 13, 0, 0, tzinfo=timezone.utc)
_PURSUIT_LAP_NAMES = ("Poursuite 2", "Poursuite 1", "Finish")


def _lap(
    start_ms: int,
    times: list[int | None],
    names: tuple[str, ...] | None = None,
    from_start: bool = True,
) -> LapInput:
    names = names or tuple(f"Loop {i}" for i in range(len(times) - 1)) + ("Finish",)
    return LapInput(
        lap_id=uuid.uuid4(),
        start_time=_T0 + timedelta(milliseconds=start_ms),
        from_start=from_start,
        crossings=tuple(CheckpointCrossing(uuid.uuid4(), name, t) for name, t in zip(names, times)),
    )


def _chain(totals: list[int | None], start_ms: int = 0, **kwargs) -> list[LapInput]:
    """Back-to-back laps (each starts where the previous finished) whose
    only checkpoint is the finish."""
    laps, cursor = [], start_ms
    for total in totals:
        laps.append(_lap(cursor, [total], **kwargs))
        cursor += total or 0
    return laps


def test_pursuit_line_names():
    assert pursuit_line("P1") == "P1"
    assert pursuit_line("p 2") == "P2"
    assert pursuit_line("Poursuite 1") == "P1"
    assert pursuit_line("Poursuite 2") == "P2"
    assert pursuit_line("Apex1") is None
    assert pursuit_line("P10") is None
    assert pursuit_line("200m") is None


def test_chained_laps_form_one_effort():
    laps = _chain([20000, 19000, 19500])
    assert len(group_continuous_laps(laps)) == 1


def test_small_gap_within_tolerance_stays_one_effort():
    laps = [_lap(0, [20000]), _lap(21000, [19000])]  # starts 1 s after the previous lap ended
    assert len(group_continuous_laps(laps, tolerance_ms=1500)) == 1
    assert len(group_continuous_laps(laps, tolerance_ms=500)) == 2


def test_pause_between_laps_splits_efforts():
    laps = _chain([20000, 19000]) + _chain([21000], start_ms=39000 + 16500)
    groups = group_continuous_laps(laps)
    assert [len(g) for g in groups] == [2, 1]


def test_unfinished_lap_ends_its_effort():
    # The lap with no finish time has no known end, so a lap starting right
    # after its start can't be chained to it.
    laps = [_lap(0, [20000]), _lap(20000, [None]), _lap(40000, [19000])]
    assert [len(g) for g in group_continuous_laps(laps)] == [2, 1]


def test_grouping_sorts_unordered_laps():
    laps = _chain([20000, 19000, 19500])
    assert [len(g) for g in group_continuous_laps(list(reversed(laps)))] == [3]


def test_standing_start_is_a_clearly_slower_first_lap():
    assert classify_start(_chain([30000, 25000, 25200])) == StartType.STANDING


def test_flying_start_when_first_lap_matches_the_rest():
    assert classify_start(_chain([26000, 25000, 25200])) == StartType.FLYING


def test_first_lap_not_from_start_is_never_standing():
    assert classify_start(_chain([30000, 25000, 25200], from_start=False)) == StartType.FLYING


def test_start_unknown_without_a_comparison_lap():
    assert classify_start(_chain([30000])) == StartType.UNKNOWN
    assert classify_start(_chain([30000, None])) == StartType.UNKNOWN
    assert classify_start([_lap(0, [None]), _lap(40000, [25000])]) == StartType.UNKNOWN


def test_standing_start_reference_uses_the_median_of_following_laps():
    # One fast follow-up lap shouldn't turn a normal first lap into a standing start.
    assert classify_start(_chain([26000, 25000, 18000, 25000])) == StartType.FLYING


def test_effort_totals_distance_and_speed_hand_checked():
    # 3 finished laps of a 250 m track in 25 s each: 750 m in 75 s = 10 m/s = 36 km/h.
    [effort] = detect_efforts(_chain([25000, 25000, 25000]), track_length_m=250)
    assert effort.completed_lap_count == 3
    assert effort.total_time_ms == 75000
    assert effort.distance_m == 750
    assert effort.avg_speed_kmh == pytest.approx(36.0)
    assert effort.best_lap_ms == 25000


def test_trailing_unfinished_lap_is_kept_but_not_counted():
    [effort] = detect_efforts(_chain([25000, 24000, None]), track_length_m=250)
    assert len(effort.laps) == 3
    assert effort.completed_lap_count == 2
    assert effort.lap_times_ms == (25000, 24000, None)
    assert effort.total_time_ms == 49000
    assert effort.distance_m == 500
    assert effort.best_lap_ms == 24000


def test_distance_and_speed_unknown_without_track_length():
    [effort] = detect_efforts(_chain([25000, 25000]))
    assert effort.total_time_ms == 50000
    assert effort.distance_m is None
    assert effort.avg_speed_kmh is None


def test_effort_with_no_finished_lap_has_no_totals():
    [effort] = detect_efforts([_lap(0, [None])], track_length_m=250)
    assert effort.completed_lap_count == 0
    assert effort.total_time_ms is None
    assert effort.distance_m is None
    assert effort.best_lap_ms is None


def test_half_lap_splits_chain_across_laps_hand_checked():
    # Each lap: P2 at 10 s, P1 at 22 s, finish at 25 s. Lap 2 starts at 25 s.
    # Timeline: P2 10, P1 22, P2 35, P1 47 -> splits 12, 13, 12.
    laps = [
        _lap(0, [10000, 22000, 25000], _PURSUIT_LAP_NAMES),
        _lap(25000, [10000, 22000, 25000], _PURSUIT_LAP_NAMES),
    ]
    splits = half_lap_splits(laps)
    assert [(s.index, s.from_line, s.to_line, s.time_ms) for s in splits] == [
        (0, "P2", "P1", 12000),
        (1, "P1", "P2", 13000),
        (2, "P2", "P1", 12000),
    ]


def test_missed_pursuit_crossing_blanks_only_the_splits_touching_it():
    laps = [
        _lap(0, [10000, 22000, 25000], _PURSUIT_LAP_NAMES),
        _lap(25000, [10000, None, 25000], _PURSUIT_LAP_NAMES),
        _lap(50000, [10000, 22000, 25000], _PURSUIT_LAP_NAMES),
    ]
    # Timeline: P2 10, P1 22, P2 35, P1 (missed), P2 60, P1 72.
    assert [s.time_ms for s in half_lap_splits(laps)] == [12000, 13000, None, None, 12000]


def test_no_half_lap_splits_without_pursuit_lines():
    assert half_lap_splits(_chain([25000, 25000])) == []


def test_detect_efforts_returns_efforts_oldest_first():
    later = _chain([25000, 25000], start_ms=500_000)
    earlier = _chain([25000], start_ms=0)
    efforts = detect_efforts(later + earlier)
    assert [len(e.laps) for e in efforts] == [1, 2]
    assert efforts[0].start_time < efforts[1].start_time


_FIXTURE = Path(__file__).parent / "fixtures" / "LS-03407.json"


def _fixture_payload() -> dict:
    return json.loads(_FIXTURE.read_text())


def test_real_export_efforts_are_continuous_blocks():
    """Every lap of the real export lands in exactly one effort, and no
    effort contains two laps whose timing doesn't chain."""
    payload = _fixture_payload()
    total_laps = 0
    effort_count = 0
    for entry in payload["eventTrainingDetails"]:
        for member in entry["trainingDetail"]["members"]:
            by_track: dict[str, list[LapInput]] = {}
            for raw in member["trainingLaps"]:
                by_track.setdefault(raw["trackId"], []).append(
                    LapInput(
                        lap_id=uuid.uuid4(),
                        start_time=datetime.fromtimestamp(raw["startTime"] / 1000, tz=timezone.utc),
                        from_start=raw["fromStart"],
                        crossings=tuple(CheckpointCrossing(uuid.uuid4(), "x", t) for t in raw["lapTimes"]),
                    )
                )
            for laps in by_track.values():
                for effort in detect_efforts(laps):
                    effort_count += 1
                    total_laps += len(effort.laps)
                    for prev, nxt in zip(effort.laps, effort.laps[1:]):
                        assert prev.total_time_ms is not None
                        assert nxt.start_time - prev.start_time == timedelta(milliseconds=prev.total_time_ms)
    assert total_laps == 936
    assert effort_count == 90


async def _signup(client, email):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "Correcthorse123!", "display_name": "Rider"}
    )
    assert resp.status_code == 201
    return resp.json()


async def _ingest_fixture(client, db_session, email="efforts@example.com"):
    from sqlalchemy import select

    from app.athletes.models import Athlete

    user = await _signup(client, email)
    async with db_session() as session:
        athlete = await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(user["id"])))
        athlete_id = athlete.id
        await create_transponder_assignment(
            session,
            athlete_id=athlete_id,
            transponder_code="LS-03407",
            start_date=date(2025, 1, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user["id"]),
            notes=None,
        )
        await session.commit()
    async with db_session() as session:
        await normalize_snapshot(session, _fixture_payload())
        await session.commit()
    return athlete_id


async def test_session_efforts_endpoint_on_real_export(client, db_session):
    athlete_id = await _ingest_fixture(client, db_session)

    resp = await client.get(f"/athletes/{athlete_id}/sessions/6a4c79ca77ee02beb78eacdb/efforts")
    assert resp.status_code == 200
    first, second = resp.json()

    # Laps 1-4 of the 2026-07-07 session chain together; lap 4 never reaches the finish.
    assert (first["index"], second["index"]) == (1, 2)
    assert first["track_name"] == "Tour complet"
    assert len(first["lap_ids"]) == 4
    assert first["lap_times_ms"] == [28041, 28614, 28299, None]
    assert first["completed_lap_count"] == 3
    assert first["total_time_ms"] == 84954
    assert first["best_lap_ms"] == 28041
    assert first["start_type"] == "flying"
    # Track length isn't ingested from sqorz, so no distance yet.
    assert first["distance_m"] is None
    assert first["avg_speed_kmh"] is None
    # P2 -> P1 -> P2 ... across the laps; the last P1 (lap 4) was never captured.
    assert [s["time_ms"] for s in first["half_lap_splits"]] == [14133, 14312, 14311, 14097, 14198, 14473, None]
    assert [(s["from_line"], s["to_line"]) for s in first["half_lap_splits"][:3]] == [
        ("P2", "P1"),
        ("P1", "P2"),
        ("P2", "P1"),
    ]

    # Laps 5-6 started after a pause; lap 6 is unfinished, so there's no lap to compare lap 5 to.
    assert len(second["lap_ids"]) == 2
    assert second["completed_lap_count"] == 1
    assert second["start_type"] == "unknown"


async def test_session_efforts_use_track_length_for_distance(client, db_session):
    from sqlalchemy import select

    from app.training.models import Track

    athlete_id = await _ingest_fixture(client, db_session, "efforts2@example.com")
    async with db_session() as session:
        track = await session.scalar(select(Track).where(Track.external_track_id == "mll61fq6"))
        track.length_m = 250
        await session.commit()

    resp = await client.get(f"/athletes/{athlete_id}/sessions/6a4c79ca77ee02beb78eacdb/efforts")
    first = resp.json()[0]
    assert first["distance_m"] == 750
    assert first["avg_speed_kmh"] == pytest.approx(750 / 84.954 * 3.6)


async def test_session_efforts_404_for_unknown_event(client, db_session):
    athlete_id = await _ingest_fixture(client, db_session, "efforts3@example.com")
    resp = await client.get(f"/athletes/{athlete_id}/sessions/nope/efforts")
    assert resp.status_code == 404

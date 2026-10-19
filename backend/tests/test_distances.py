import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.athletes.models import Athlete
from app.connections.service import create_transponder_assignment
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.training.distances import (
    STANDARD_EVENTS,
    best_lap_window,
    event_lap_count,
    lap_windows,
    laps_for_distance,
)
from app.training.efforts import CheckpointCrossing, LapInput, StartType, detect_efforts
from app.training.models import Track

_T0 = datetime(2026, 7, 7, 13, 0, 0, tzinfo=timezone.utc)


def _efforts(totals: list[int | None], start_ms: int = 0):
    laps, cursor = [], start_ms
    for total in totals:
        laps.append(
            LapInput(
                lap_id=uuid.uuid4(),
                start_time=_T0 + timedelta(milliseconds=cursor),
                from_start=True,
                crossings=(CheckpointCrossing(uuid.uuid4(), "Finish", total),),
            )
        )
        cursor += total or 0
    return detect_efforts(laps, 250)


def test_laps_for_distance():
    assert laps_for_distance(500, 250) == 2
    assert laps_for_distance(750, 250) == 3
    assert laps_for_distance(4000, 250) == 16
    assert laps_for_distance(250, 250) == 1
    # Not a whole number of laps, shorter than a lap, or no known length.
    assert laps_for_distance(200, 250) is None
    assert laps_for_distance(500, 333.33) is None
    assert laps_for_distance(500, None) is None
    assert laps_for_distance(0, 250) is None
    # A slightly rounded entered length still counts.
    assert laps_for_distance(1000, 333.3) == 3


def test_standard_event_lap_counts_on_a_250m_track():
    counts = {e.key: event_lap_count(e, 250) for e in STANDARD_EVENTS}
    assert counts == {
        "f200": None,  # timed by the 200m view, not whole laps
        "lap": 1,
        "500m": 2,
        "750m": 3,
        "1km": 4,
        "2km": 8,
        "3km": 12,
        "4km": 16,
    }


def test_standard_event_lap_counts_without_track_length():
    counts = {e.key: event_lap_count(e, None) for e in STANDARD_EVENTS}
    assert counts["lap"] == 1
    assert counts["500m"] is None


def test_lap_windows_hand_checked_and_start_types():
    # Standing start (30 s first lap vs ~25 s), then three more laps.
    [effort] = _efforts([30000, 25000, 24000, 26000])
    assert effort.start_type == StartType.STANDING
    windows = lap_windows(effort, 2)
    assert [(w.first_lap_index, w.time_ms, w.start_type) for w in windows] == [
        (0, 55000, StartType.STANDING),
        (1, 49000, StartType.FLYING),
        (2, 50000, StartType.FLYING),
    ]


def test_window_cannot_include_an_unfinished_lap():
    [effort] = _efforts([30000, 25000, None])
    assert [w.first_lap_index for w in lap_windows(effort, 2)] == [0]
    assert lap_windows(effort, 3) == []


def test_window_longer_than_the_effort_does_not_exist():
    [effort] = _efforts([25000, 25000])
    assert lap_windows(effort, 3) == []


def test_best_window_across_efforts_and_start_type_filter():
    first = _efforts([30000, 25000, 24000, 26000])
    second = _efforts([27000, 26500, 26000], start_ms=1_000_000)
    efforts = first + second

    best = best_lap_window(efforts, 2)
    assert best is not None and best.time_ms == 49000
    standing = best_lap_window(efforts, 2, StartType.STANDING)
    assert standing is not None and standing.time_ms == 55000
    assert best_lap_window(efforts, 2, StartType.UNKNOWN) is None
    assert best_lap_window(efforts, 5) is None


def _payload(transponder: str, laps_totals: list[int], event_id: str = "evt-pursuit") -> dict:
    """One session with back-to-back laps; each lap has a mid checkpoint at
    40% of its time and the finish."""
    laps, cursor = [], 0
    start0 = _T0
    for i, total in enumerate(laps_totals):
        start = start0 + timedelta(milliseconds=cursor)
        laps.append(
            {
                "lapId": f"{event_id}-{i}",
                "trackId": "trk1",
                "classCode": "A",
                "startTime": int(start.timestamp() * 1000),
                "lapTimes": [int(total * 0.4), total],
                "fromStart": True,
                "startNumber": i + 1,
            }
        )
        cursor += total
    return {
        "transponderCode": transponder,
        "eventTrainingDetails": [
            {
                "accountId": "acc-1",
                "accountName": "TestClub",
                "cacheSeconds": 60,
                "trainingDetail": {
                    "eventId": event_id,
                    "eventName": "Pursuit day",
                    "eventDate": "2026-07-07",
                    "sportType": "track",
                    "classes": [{"classCode": "A", "className": "Test", "classType": "open"}],
                    "tracks": [
                        {
                            "trackId": "trk1",
                            "trackName": "Test Track",
                            "trackType": "circuit",
                            "trackEnabled": True,
                            "trackGate": False,
                            "trackStartFrom": "start",
                            "validationMethod": "time",
                            "trackLoops": [
                                {"loopId": "trk1/1", "loopName": "Mid", "distance": 100},
                                {"loopId": "trk1/2", "loopName": "Finish", "distance": 250},
                            ],
                            "trackViews": [],
                        }
                    ],
                    "members": [{"classCode": "A", "transponder": transponder, "gender": 0, "trainingLaps": laps}],
                    "groups": [],
                    "lowBatteryTransponders": [],
                    "maxTrainingHours": 24,
                    "startTimestamp": _T0.isoformat().replace("+00:00", "Z"),
                    "endTimestamp": _T0.isoformat().replace("+00:00", "Z"),
                },
            }
        ],
    }


async def _setup(client, db_session, email: str, laps_totals: list[int], track_length_m: float | None):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "Correcthorse123!", "display_name": "Rider"}
    )
    user = resp.json()
    async with db_session() as session:
        athlete = await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(user["id"])))
        athlete_id = athlete.id
        await create_transponder_assignment(
            session,
            athlete_id=athlete_id,
            transponder_code="TP-D",
            start_date=date(2026, 1, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user["id"]),
            notes=None,
        )
        await session.commit()
    async with db_session() as session:
        await normalize_snapshot(session, _payload("TP-D", laps_totals))
        track = await session.scalar(select(Track).where(Track.external_track_id == "trk1"))
        track.length_m = track_length_m
        track_id = track.id
        await session.commit()
    return athlete_id, track_id


async def test_progression_custom_distance_spans_laps_in_an_effort(client, db_session):
    # 6 laps: standing first lap, then ~25 s laps. Best 4-lap run is laps 2-5.
    totals = [31000, 26000, 25000, 24000, 25500, 27000]
    athlete_id, track_id = await _setup(client, db_session, "dist1@example.com", totals, 250)

    resp = await client.get(
        f"/athletes/{athlete_id}/progression",
        params={"metric": "custom_distance", "track_id": track_id, "distance_m": 1000},
    )
    assert resp.status_code == 200
    [point] = resp.json()
    # windows: [0:4]=106000, [1:5]=100500, [2:6]=101500
    assert point["time_ms"] == 100500
    assert point["achieved_distance_m"] == 1000
    assert point["best_lap_id"]

    standing = await client.get(
        f"/athletes/{athlete_id}/progression",
        params={"metric": "custom_distance", "track_id": track_id, "distance_m": 1000, "start_type": "standing"},
    )
    assert [p["time_ms"] for p in standing.json()] == [106000]

    flying = await client.get(
        f"/athletes/{athlete_id}/progression",
        params={"metric": "custom_distance", "track_id": track_id, "distance_m": 1000, "start_type": "flying"},
    )
    assert [p["time_ms"] for p in flying.json()] == [100500]


async def test_progression_custom_distance_needs_enough_laps(client, db_session):
    athlete_id, track_id = await _setup(client, db_session, "dist2@example.com", [26000, 25000], 250)
    resp = await client.get(
        f"/athletes/{athlete_id}/progression",
        params={"metric": "custom_distance", "track_id": track_id, "distance_m": 1000},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_progression_custom_distance_falls_back_to_single_lap_without_track_length(client, db_session):
    athlete_id, track_id = await _setup(client, db_session, "dist3@example.com", [26000, 25000, 24000, 25000], None)
    resp = await client.get(
        f"/athletes/{athlete_id}/progression",
        params={"metric": "custom_distance", "track_id": track_id, "distance_m": 1000},
    )
    assert resp.status_code == 200
    [point] = resp.json()
    # Single-lap search: the closest in-lap window to 1000 m is the whole 250 m lap.
    assert point["achieved_distance_m"] == pytest.approx(250)
    assert point["time_ms"] == 24000

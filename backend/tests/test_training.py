import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.athletes.models import Athlete
from app.connections.service import create_transponder_assignment
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.training.models import LapSegmentTime, Track, TrackLoop, TrainingEvent, TrainingLap
from app.training.service import (
    DistancedSegment,
    _segment_deltas,
    _view_time_ms,
    _whole_lap_time_ms,
    find_best_distance_window,
)


def _epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _track_payload() -> dict:
    return {
        "trackId": "trk1",
        "trackName": "Test Track",
        "trackType": "circuit",
        "trackEnabled": True,
        "trackGate": False,
        "trackStartFrom": "start",
        "validationMethod": "time",
        "trackLoops": [
            {"loopId": "trk1/1", "loopName": "Loop A", "distance": 80},
            {"loopId": "trk1/2", "loopName": "Loop B", "distance": 150},
            {"loopId": "trk1/3", "loopName": "Finish", "distance": 200},
        ],
        "trackViews": [
            {"trackViewId": "view1", "trackViewName": "Flying A", "trackViewLoops": [{"loopId": "trk1/1"}]}
        ],
    }


def _event_payload(event_id: str, event_date: str, lap_id: str, start: datetime, lap_times: list, transponder_code: str) -> dict:
    return {
        "accountId": "acc-1",
        "accountName": "TestClub",
        "cacheSeconds": 60,
        "trainingDetail": {
            "eventId": event_id,
            "eventName": f"Session {event_date}",
            "eventDate": event_date,
            "sportType": "bmx",
            "classes": [{"classCode": "A", "className": "Test class", "classType": "open"}],
            "tracks": [_track_payload()],
            "members": [
                {
                    "classCode": "A",
                    "transponder": transponder_code,
                    "gender": 0,
                    "trainingLaps": [
                        {
                            "lapId": lap_id,
                            "trackId": "trk1",
                            "classCode": "A",
                            "startTime": _epoch_ms(start),
                            "lapTimes": lap_times,
                            "fromStart": True,
                            "startNumber": 1,
                        }
                    ],
                }
            ],
            "groups": [],
            "lowBatteryTransponders": [],
            "maxTrainingHours": 24,
            "startTimestamp": start.isoformat().replace("+00:00", "Z"),
            "endTimestamp": start.isoformat().replace("+00:00", "Z"),
        },
    }


def _make_payload(transponder_code: str = "TP-1") -> dict:
    return {
        "transponderCode": transponder_code,
        "eventTrainingDetails": [
            _event_payload(
                "evt1",
                "2026-06-05",
                "lap1-1",
                datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc),
                [5000, 9000, 14500],
                transponder_code,
            ),
            _event_payload(
                "evt2",
                "2026-06-20",
                "lap2-1",
                datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
                [4800, 8800, 13600],
                transponder_code,
            ),
        ],
    }


async def _signup(client, email, display_name="Someone"):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "Correcthorse123!", "display_name": display_name}
    )
    assert resp.status_code == 201
    return resp.json()


async def _self_athlete_id(db_session, user_id: str) -> uuid.UUID:
    async with db_session() as session:
        athlete = await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(user_id)))
        return athlete.id


def test_find_best_distance_window_hand_checked():
    segments = [
        DistancedSegment(distance_m=80, time_ms=5000),
        DistancedSegment(distance_m=70, time_ms=6000),
        DistancedSegment(distance_m=50, time_ms=4000),
    ]
    result = find_best_distance_window(segments, target_distance_m=150)
    assert result is not None
    assert (result.start_index, result.end_index) == (0, 1)
    assert result.distance_m == 150
    assert result.time_ms == 11000


def test_find_best_distance_window_cannot_cross_unknown_distance_segment():
    segments = [
        DistancedSegment(distance_m=None, time_ms=1000),
        DistancedSegment(distance_m=100, time_ms=2000),
    ]
    result = find_best_distance_window(segments, target_distance_m=100)
    assert result is not None
    assert (result.start_index, result.end_index) == (1, 1)
    assert result.distance_m == 100
    assert result.time_ms == 2000


_LS03407_FIXTURE = Path(__file__).parent / "fixtures" / "LS-03407.json"


def _load_ls03407_lap() -> tuple[list[int | None], list[int]]:
    """Pull one real lap out of an actual sqorz export: its raw cumulative
    `lapTimes`, and the segment positions the file's own "200m" view refers
    to. Real sqorz lapTimes are cumulative-since-lap-start per checkpoint,
    not independent per-segment durations (index 5's capture was missed)."""
    payload = json.loads(_LS03407_FIXTURE.read_text())
    detail = payload["eventTrainingDetails"][0]["trainingDetail"]
    track = detail["tracks"][0]
    loops = track["trackLoops"]
    loop_id_to_index = {loop["loopId"]: idx for idx, loop in enumerate(loops)}

    view_200m = next(v for v in track["trackViews"] if v["trackViewName"] == "200m")
    view_indexes = [loop_id_to_index[ref["loopId"]] for ref in view_200m["trackViewLoops"]]

    member = detail["members"][0]
    lap = next(lap for lap in member["trainingLaps"] if lap["trackId"] == track["trackId"])
    return lap["lapTimes"], view_indexes


_CUMULATIVE_TIME_MS, _LS03407_200M_VIEW_INDEXES = _load_ls03407_lap()


def _make_segments(times_ms: list[int | None], distances_m: list[float | None] | None = None) -> list[LapSegmentTime]:
    loop_ids = [uuid.uuid4() for _ in times_ms]
    segments = []
    for i, time_ms in enumerate(times_ms):
        segment = LapSegmentTime(sequence_index=i, time_ms=time_ms, track_loop_id=loop_ids[i])
        if distances_m is not None:
            segment.track_loop = TrackLoop(distance_m=distances_m[i])
        segments.append(segment)
    return segments


def test_whole_lap_time_is_last_checkpoints_cumulative_value():
    segments = _make_segments(_CUMULATIVE_TIME_MS)
    assert _whole_lap_time_ms(segments) == 28041


def test_whole_lap_time_none_when_finish_capture_missing():
    segments = _make_segments([5207, 5488, None])
    assert _whole_lap_time_ms(segments) is None


def test_whole_lap_time_none_for_empty_segments():
    assert _whole_lap_time_ms([]) is None


def test_view_time_is_gate_to_gate_subtraction_not_sum():
    segments = _make_segments(_CUMULATIVE_TIME_MS)
    loop_ids = [s.track_loop_id for s in segments]

    # positions 2-4: 19222 - 12191 (both ends are gates with their own reading)
    assert _view_time_ms(segments, [loop_ids[2], loop_ids[3], loop_ids[4]]) == 7031

    # positions 4-6: interior null at position 5 isn't touched by either gate
    assert _view_time_ms(segments, [loop_ids[4], loop_ids[5], loop_ids[6]]) == 7102

    # view's own end gate (position 5) is missing
    assert _view_time_ms(segments, [loop_ids[4], loop_ids[5]]) is None

    # view's own start gate (position 5) is missing
    assert _view_time_ms(segments, [loop_ids[5], loop_ids[7]]) is None

    # adjacent positions 0-1: matches _segment_deltas's delta for position 1
    assert _view_time_ms(segments, [loop_ids[0], loop_ids[1]]) == 281

    # single-loop view: elapsed since lap start to that one checkpoint
    assert _view_time_ms(segments, [loop_ids[0]]) == 5207

    # loop not present in this lap at all
    assert _view_time_ms(segments, [uuid.uuid4()]) is None


def test_view_time_matches_real_flying_200_example():
    # Real sqorz track (LS-03407), using the file's own "200m" view
    # (spanning [200m, 100m, Finish]) against that lap's real lapTimes.
    segments = _make_segments(_CUMULATIVE_TIME_MS)
    loop_ids = [s.track_loop_id for s in segments]
    view_loop_ids = [loop_ids[i] for i in _LS03407_200M_VIEW_INDEXES]

    assert _view_time_ms(segments, view_loop_ids) == 22553


def test_segment_deltas_converts_cumulative_time_independently_from_distance():
    distances_m = [50, 100, 150, 200, 250, 300, 350, 400]
    segments = _make_segments(_CUMULATIVE_TIME_MS, distances_m=distances_m)

    deltas = _segment_deltas(segments)

    assert [d.time_ms for d in deltas] == [5207, 281, 6703, 4459, 2572, None, None, 1717]
    assert [d.distance_m for d in deltas] == [50, 50, 50, 50, 50, 50, 50, 50]


async def test_normalize_snapshot_attributes_laps_to_correct_athlete_by_date_range(client, db_session):
    from httpx import ASGITransport, AsyncClient

    from app.main import app as real_app

    user_a = await _signup(client, "trainA@example.com")
    athlete_a_id = await _self_athlete_id(db_session, user_a["id"])

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as other_client:
        user_b = await _signup(other_client, "trainB@example.com")
        athlete_b_id = await _self_athlete_id(db_session, user_b["id"])

    async with db_session() as session:
        await create_transponder_assignment(
            session,
            athlete_id=athlete_a_id,
            transponder_code="TP-1",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 10),
            created_by_user_id=uuid.UUID(user_a["id"]),
            notes=None,
        )
        await session.commit()

    async with db_session() as session:
        await create_transponder_assignment(
            session,
            athlete_id=athlete_b_id,
            transponder_code="TP-1",
            start_date=date(2026, 6, 15),
            end_date=date(2026, 6, 25),
            created_by_user_id=uuid.UUID(user_b["id"]),
            notes=None,
        )
        await session.commit()

    async with db_session() as session:
        await normalize_snapshot(session, _make_payload())
        await session.commit()

    async with db_session() as session:
        lap1 = await session.scalar(select(TrainingLap).where(TrainingLap.external_lap_id == "lap1-1"))
        lap2 = await session.scalar(select(TrainingLap).where(TrainingLap.external_lap_id == "lap2-1"))
        assert lap1.athlete_id == athlete_a_id
        assert lap2.athlete_id == athlete_b_id

        track = await session.scalar(select(Track).where(Track.external_track_id == "trk1"))
        assert track is not None
        assert track.name == "Test Track"

        loops = (await session.scalars(select(TrackLoop).where(TrackLoop.track_id == track.id))).all()
        assert {loop.external_loop_id: loop.distance_m for loop in loops} == {
            "trk1/1": 80.0,
            "trk1/2": 150.0,
            "trk1/3": 200.0,
        }

        segments = (
            await session.scalars(
                select(LapSegmentTime)
                .where(LapSegmentTime.training_lap_id == lap1.id)
                .order_by(LapSegmentTime.sequence_index)
            )
        ).all()
        assert [s.time_ms for s in segments] == [5000, 9000, 14500]


async def test_normalize_snapshot_drops_events_for_transponder_without_assignment(client, db_session):
    user = await _signup(client, "trainE@example.com")
    await _self_athlete_id(db_session, user["id"])  # ensures athlete row exists, unused here

    async with db_session() as session:
        await normalize_snapshot(session, _make_payload(transponder_code="TP-UNASSIGNED"))
        await session.commit()

    async with db_session() as session:
        lap = await session.scalar(select(TrainingLap).where(TrainingLap.external_lap_id == "lap1-1"))
        assert lap is None
        event = await session.scalar(select(TrainingEvent).where(TrainingEvent.external_event_id == "evt1"))
        assert event is None


async def test_normalize_snapshot_drops_event_dates_outside_assignment_window(client, db_session):
    user = await _signup(client, "trainH@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    async with db_session() as session:
        await create_transponder_assignment(
            session,
            athlete_id=athlete_id,
            transponder_code="TP-WINDOW",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 10),
            created_by_user_id=uuid.UUID(user["id"]),
            notes=None,
        )
        await session.commit()

    async with db_session() as session:
        await normalize_snapshot(session, _make_payload(transponder_code="TP-WINDOW"))
        await session.commit()

    async with db_session() as session:
        # evt1 (2026-06-05) is inside the assignment window; evt2 (2026-06-20) is not.
        in_window = await session.scalar(select(TrainingEvent).where(TrainingEvent.external_event_id == "evt1"))
        out_of_window = await session.scalar(select(TrainingEvent).where(TrainingEvent.external_event_id == "evt2"))
        assert in_window is not None
        assert out_of_window is None


async def test_normalize_snapshot_gives_each_athlete_their_own_event_copy(client, db_session):
    user_a = await _signup(client, "trainI@example.com")
    athlete_a_id = await _self_athlete_id(db_session, user_a["id"])

    from httpx import ASGITransport, AsyncClient

    from app.main import app as real_app

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as other_client:
        user_b = await _signup(other_client, "trainJ@example.com")
        athlete_b_id = await _self_athlete_id(db_session, user_b["id"])

    async with db_session() as session:
        await create_transponder_assignment(
            session,
            athlete_id=athlete_a_id,
            transponder_code="TP-SHARED-A",
            start_date=date(2026, 6, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user_a["id"]),
            notes=None,
        )
        await create_transponder_assignment(
            session,
            athlete_id=athlete_b_id,
            transponder_code="TP-SHARED-B",
            start_date=date(2026, 6, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user_b["id"]),
            notes=None,
        )
        await session.commit()

    shared_event_id = "evt-shared"
    payload_a = {
        "transponderCode": "TP-SHARED-A",
        "eventTrainingDetails": [
            _event_payload(
                shared_event_id,
                "2026-06-05",
                "lap-shared-a",
                datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc),
                [5000, 6000, 4000],
                "TP-SHARED-A",
            )
        ],
    }
    payload_b = {
        "transponderCode": "TP-SHARED-B",
        "eventTrainingDetails": [
            _event_payload(
                shared_event_id,
                "2026-06-05",
                "lap-shared-b",
                datetime(2026, 6, 5, 10, 0, 5, tzinfo=timezone.utc),
                [5100, 6100, 4100],
                "TP-SHARED-B",
            )
        ],
    }

    async with db_session() as session:
        await normalize_snapshot(session, payload_a)
        await normalize_snapshot(session, payload_b)
        await session.commit()

    async with db_session() as session:
        events = (
            await session.scalars(select(TrainingEvent).where(TrainingEvent.external_event_id == shared_event_id))
        ).all()
        assert len(events) == 2
        events_by_athlete = {e.athlete_id: e for e in events}
        assert set(events_by_athlete) == {athlete_a_id, athlete_b_id}

        lap_a = await session.scalar(select(TrainingLap).where(TrainingLap.external_lap_id == "lap-shared-a"))
        lap_b = await session.scalar(select(TrainingLap).where(TrainingLap.external_lap_id == "lap-shared-b"))
        assert lap_a.athlete_id == athlete_a_id
        assert lap_b.athlete_id == athlete_b_id


async def test_session_detail_and_progression_endpoints(client, db_session):
    user = await _signup(client, "trainC@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    async with db_session() as session:
        await create_transponder_assignment(
            session,
            athlete_id=athlete_id,
            transponder_code="TP-2",
            start_date=date(2026, 6, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user["id"]),
            notes=None,
        )
        await session.commit()

    async with db_session() as session:
        await normalize_snapshot(session, _make_payload(transponder_code="TP-2"))
        await session.commit()

    session_resp = await client.get(f"/athletes/{athlete_id}/sessions/evt1")
    assert session_resp.status_code == 200
    body = session_resp.json()
    assert body["external_event_id"] == "evt1"
    assert len(body["tracks"]) == 1
    track_detail = body["tracks"][0]
    assert track_detail["track_name"] == "Test Track"
    assert len(track_detail["laps"]) == 1
    lap = track_detail["laps"][0]
    assert lap["whole_lap_time_ms"] == 14500
    assert [s["time_ms"] for s in lap["segments"]] == [5000, 4000, 5500]
    view = next(v for v in lap["views"] if v["name"] == "Flying A")
    assert view["time_ms"] == 5000

    track_id = track_detail["track_id"]
    view_id = view["track_view_id"]

    lap_time_resp = await client.get(
        f"/athletes/{athlete_id}/progression", params={"metric": "lap_time", "track_id": track_id}
    )
    assert lap_time_resp.status_code == 200
    points = lap_time_resp.json()
    assert [p["time_ms"] for p in points] == [14500, 13600]

    view_resp = await client.get(
        f"/athletes/{athlete_id}/progression", params={"metric": "view", "track_view_id": view_id}
    )
    assert view_resp.status_code == 200
    assert [p["time_ms"] for p in view_resp.json()] == [5000, 4800]

    custom_resp = await client.get(
        f"/athletes/{athlete_id}/progression",
        params={"metric": "custom_distance", "track_id": track_id, "distance_m": 150},
    )
    assert custom_resp.status_code == 200
    custom_points = custom_resp.json()
    assert custom_points[0]["time_ms"] == 9000
    assert custom_points[0]["achieved_distance_m"] == 150
    assert custom_points[1]["time_ms"] == 8800


async def test_list_sessions_and_tracks_endpoints(client, db_session):
    user = await _signup(client, "trainG@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    async with db_session() as session:
        await create_transponder_assignment(
            session,
            athlete_id=athlete_id,
            transponder_code="TP-3",
            start_date=date(2026, 6, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user["id"]),
            notes=None,
        )
        await session.commit()

    async with db_session() as session:
        await normalize_snapshot(session, _make_payload(transponder_code="TP-3"))
        await session.commit()

    async with db_session() as session:
        track = await session.scalar(select(Track).where(Track.external_track_id == "trk1"))
        session.add(TrackLoop(track_id=track.id, external_loop_id="trk1/4", name="50m", distance_m=None))
        await session.commit()

    sessions_resp = await client.get(f"/athletes/{athlete_id}/sessions")
    assert sessions_resp.status_code == 200
    sessions_body = sessions_resp.json()
    assert [s["external_event_id"] for s in sessions_body] == ["evt2", "evt1"]

    tracks_resp = await client.get(f"/athletes/{athlete_id}/tracks")
    assert tracks_resp.status_code == 200
    tracks_body = tracks_resp.json()
    assert len(tracks_body) == 1
    assert tracks_body[0]["name"] == "Test Track"
    assert [v["name"] for v in tracks_body[0]["views"]] == ["Flying A"]
    # A loop with no reported distance (sqorz sporadically omits it) still comes through,
    # sorted after every loop with a known distance rather than being dropped.
    assert [(loop["name"], loop["distance_m"]) for loop in tracks_body[0]["loops"]] == [
        ("Loop A", 80),
        ("Loop B", 150),
        ("Finish", 200),
        ("50m", None),
    ]
    assert tracks_body[0]["length_m"] is None


async def test_session_detail_404_for_unknown_event(client, db_session):
    user = await _signup(client, "trainD@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    resp = await client.get(f"/athletes/{athlete_id}/sessions/does-not-exist")
    assert resp.status_code == 404


async def test_progression_requires_metric_specific_params(client, db_session):
    user = await _signup(client, "trainF@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    resp = await client.get(f"/athletes/{athlete_id}/progression", params={"metric": "lap_time"})
    assert resp.status_code == 422

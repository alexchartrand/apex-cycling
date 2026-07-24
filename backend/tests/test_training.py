import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.athletes.models import Athlete
from app.connections.service import create_transponder_assignment
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.training.models import LapSegmentTime, Track, TrackLoop, TrainingEvent, TrainingLap
from app.training.service import DistancedSegment, find_best_distance_window


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
                [5000, 6000, 4000],
                transponder_code,
            ),
            _event_payload(
                "evt2",
                "2026-06-20",
                "lap2-1",
                datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
                [4800, 5800, 3900],
                transponder_code,
            ),
        ],
    }


async def _signup(client, email, display_name="Someone"):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "correcthorse", "display_name": display_name}
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


async def test_normalize_snapshot_attributes_laps_to_correct_athlete_by_date_range(client, db_session):
    from httpx import ASGITransport, AsyncClient

    from app.main import app as real_app

    user_a = await _signup(client, "trainA@example.com")
    athlete_a_id = await _self_athlete_id(db_session, user_a["id"])

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test") as other_client:
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
        assert [s.time_ms for s in segments] == [5000, 6000, 4000]


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

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test") as other_client:
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
    assert lap["whole_lap_time_ms"] == 15000
    assert [s["time_ms"] for s in lap["segments"]] == [5000, 6000, 4000]
    view = next(v for v in lap["views"] if v["name"] == "Flying A")
    assert view["time_ms"] == 5000

    track_id = track_detail["track_id"]
    view_id = view["track_view_id"]

    lap_time_resp = await client.get(
        f"/athletes/{athlete_id}/progression", params={"metric": "lap_time", "track_id": track_id}
    )
    assert lap_time_resp.status_code == 200
    points = lap_time_resp.json()
    assert [p["time_ms"] for p in points] == [15000, 14500]

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
    assert custom_points[0]["time_ms"] == 11000
    assert custom_points[0]["achieved_distance_m"] == 150
    assert custom_points[1]["time_ms"] == 10600


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

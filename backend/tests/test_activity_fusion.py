"""A recording joined to the sqorz session it contains: auto-linking, the
device clock offset, per-lap and per-effort power, and who may see it."""

import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.activities import streams
from app.activities.models import Activity, ActivitySource, ActivityStream
from app.athletes.models import CoachAthlete, CoachAthleteStatus
from app.connections.service import create_transponder_assignment
from app.core.config import get_settings
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.ingestion.sqorz.normalizer_adapter import SqlAlchemyRecordsAdapter
from app.main import app as real_app
from app.training.models import TrainingEvent
from tests.fit_builder import build_fit
from tests.test_account import _rows_referencing, _signup
from tests.test_training import _epoch_ms, _track_payload

SESSION_START = datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc)
# A warm-up, two efforts and a cool-down, in seconds per lap.
LAP_TIMES = [24, 22, 20, 19, 18, 17.5, 17.2, 17, 18, 21, 25, 28, 26, 22, 19, 17.8, 17.3, 17.1, 17, 17.4, 19, 23, 27, 30]
DEVICE_BEHIND_S = 12.0  # sqorz time = device time + 12 s
TRANSPONDER = "TP-F"


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


def _lap_starts() -> list[float]:
    starts, clock = [], 0.0
    for duration in LAP_TIMES:
        starts.append(clock)
        clock += duration
    return starts


def _session_payload(event_id: str = "evt-f", start: datetime = SESSION_START) -> dict:
    laps = []
    for index, (offset, duration) in enumerate(zip(_lap_starts(), LAP_TIMES)):
        ms = round(duration * 1000)
        laps.append(
            {
                "lapId": f"{event_id}-lap{index}",
                "trackId": "trk1",
                "classCode": "A",
                "startTime": _epoch_ms(start + timedelta(seconds=offset)),
                "lapTimes": [round(ms * 0.3), round(ms * 0.65), ms],
                "fromStart": index == 0,
                "startNumber": 1,
            }
        )
    return {
        "transponderCode": TRANSPONDER,
        "eventTrainingDetails": [
            {
                "accountId": "acc-1",
                "accountName": "TestClub",
                "cacheSeconds": 60,
                "trainingDetail": {
                    "eventId": event_id,
                    "eventName": "Track night",
                    "eventDate": start.date().isoformat(),
                    "sportType": "track",
                    "classes": [{"classCode": "A", "className": "Open", "classType": "open"}],
                    "tracks": [_track_payload()],
                    "members": [{"classCode": "A", "transponder": TRANSPONDER, "trainingLaps": laps}],
                    "groups": [],
                    "lowBatteryTransponders": [],
                    "maxTrainingHours": 24,
                    "startTimestamp": start.isoformat().replace("+00:00", "Z"),
                    "endTimestamp": (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
                },
            }
        ],
    }


def _recording(device_behind_s: float = DEVICE_BEHIND_S, with_speed: bool = True, lead_s: int = 120) -> bytes:
    """What a head unit would record riding that session: speed and power
    follow the lap times. Its clock runs `device_behind_s` behind sqorz's."""
    device_start = SESSION_START - timedelta(seconds=lead_s)
    total = lead_s + int(sum(LAP_TIMES)) + 300
    starts = _lap_starts()
    records = []
    for t in range(total):
        into_session = t + device_behind_s - lead_s  # sqorz seconds since the first lap started
        lap = next((i for i, s in enumerate(starts) if s <= into_session < s + LAP_TIMES[i]), None)
        speed = 250 / LAP_TIMES[lap] if lap is not None else 3.0
        record = {"t": t, "power": round(5000 / LAP_TIMES[lap]) if lap is not None else 80, "heart_rate": 150,
                  "cadence": 100 if lap is not None else 60}  # fmt: skip
        if with_speed:
            record["speed"] = speed
        records.append(record)
    return build_fit(device_start, records)


async def _athlete_with_session(client, db_session, *, email="rider@example.com", with_session=True) -> str:
    user = await _signup(client, email)
    athlete_id = (await client.get("/athletes/me")).json()["id"]
    async with db_session() as session:
        await create_transponder_assignment(
            session,
            athlete_id=uuid.UUID(athlete_id),
            transponder_code=TRANSPONDER,
            start_date=date(2026, 6, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user["id"]),
            notes=None,
        )
        await session.commit()
    if with_session:
        await _ingest(db_session)
    return athlete_id


async def _ingest(db_session) -> None:
    async with db_session() as session:
        athlete_ids = await normalize_snapshot(session, _session_payload())
        await SqlAlchemyRecordsAdapter(session).recompute(athlete_ids)
        await session.commit()


async def _upload(client, athlete_id: str, content: bytes) -> dict:
    resp = await client.post(
        f"/athletes/{athlete_id}/activities/upload", files=[("files", ("ride.fit", content, "application/octet-stream"))]
    )
    return resp.json()[0]["activity"]


@asynccontextmanager
async def _coach_of(db_session, athlete_id: str):
    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as coach_client:
        coach = await _signup(coach_client, "coach@example.com")
        async with db_session() as session:
            session.add(
                CoachAthlete(
                    coach_user_id=uuid.UUID(coach["id"]), athlete_id=uuid.UUID(athlete_id), status=CoachAthleteStatus.ACTIVE
                )
            )
            await session.commit()
        yield coach_client


# --- linking -----------------------------------------------------------------


async def test_an_upload_links_to_its_session_and_finds_the_clock_offset(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)

    activity = await _upload(client, athlete_id, _recording())

    assert activity["external_event_id"] == "evt-f"
    assert activity["clock_offset_s"] == pytest.approx(DEVICE_BEHIND_S, abs=1.0)
    assert activity["session_link_manual"] is False


async def test_a_ride_with_no_session_stays_unlinked(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, with_session=False)
    activity = await _upload(client, athlete_id, _recording())
    assert activity["external_event_id"] is None and activity["clock_offset_s"] == 0


async def test_a_session_synced_after_the_upload_picks_up_the_recording(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, with_session=False)
    activity = await _upload(client, athlete_id, _recording())
    assert activity["external_event_id"] is None

    await _ingest(db_session)  # the next sqorz poll brings the laps

    linked = (await client.get(f"/athletes/{athlete_id}/activities/{activity['id']}")).json()
    assert linked["external_event_id"] == "evt-f"
    assert linked["clock_offset_s"] == pytest.approx(DEVICE_BEHIND_S, abs=1.0)


async def test_without_a_speed_trace_the_offset_stays_zero_but_the_link_is_made(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)
    activity = await _upload(client, athlete_id, _recording(with_speed=False))
    assert activity["external_event_id"] == "evt-f" and activity["clock_offset_s"] == 0


async def test_unlinking_sticks_and_relinking_is_manual(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)
    activity = await _upload(client, athlete_id, _recording())
    url = f"/athletes/{athlete_id}/activities/{activity['id']}/session"

    unlinked = (await client.delete(url)).json()
    assert unlinked["external_event_id"] is None and unlinked["session_link_manual"] is True
    await _ingest(db_session)  # auto-linking runs again and leaves it alone
    assert (await client.get(f"/athletes/{athlete_id}/activities/{activity['id']}")).json()["external_event_id"] is None

    relinked = (await client.put(url, json={"external_event_id": "evt-f", "clock_offset_s": 5.5})).json()
    assert relinked["external_event_id"] == "evt-f" and relinked["clock_offset_s"] == 5.5
    assert relinked["session_link_manual"] is True
    # Without an offset it is estimated again.
    again = (await client.put(url, json={"external_event_id": "evt-f"})).json()
    assert again["clock_offset_s"] == pytest.approx(DEVICE_BEHIND_S, abs=1.0)


async def test_linking_to_an_unknown_session_or_with_an_absurd_offset_is_refused(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)
    activity = await _upload(client, athlete_id, _recording())
    url = f"/athletes/{athlete_id}/activities/{activity['id']}/session"
    assert (await client.put(url, json={"external_event_id": "nope"})).status_code == 404
    assert (await client.put(url, json={"external_event_id": "evt-f", "clock_offset_s": 99999})).status_code == 422


async def test_suggestion_reports_session_offset_and_confidence(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, with_session=False)
    activity = await _upload(client, athlete_id, _recording())
    url = f"/athletes/{athlete_id}/activities/{activity['id']}/session/suggestion"

    nothing = (await client.get(url)).json()
    assert nothing["external_event_id"] is None and nothing["confident"] is False

    await _ingest(db_session)
    async with db_session() as session:  # undo the auto-link to see a bare suggestion
        row = await session.get(Activity, uuid.UUID(activity["id"]))
        row.training_event_id, row.clock_offset_s = None, 0.0
        row.session_link_manual = True
        await session.commit()
    suggestion = (await client.get(url)).json()
    assert suggestion["external_event_id"] == "evt-f" and suggestion["event_name"] == "Track night"
    assert suggestion["clock_offset_s"] == pytest.approx(DEVICE_BEHIND_S, abs=1.0)
    assert suggestion["confident"] is True and suggestion["correlation"] > 0.95 and suggestion["laps_used"] >= 19


# --- what the lap table gets -------------------------------------------------


async def test_laps_and_efforts_carry_the_recordings_power_heart_rate_and_cadence(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)
    await _upload(client, athlete_id, _recording())

    detail = (await client.get(f"/athletes/{athlete_id}/sessions/evt-f")).json()
    (linked,) = detail["activities"]
    assert linked["has_power"] and linked["has_heart_rate"] and linked["has_cadence"]
    assert linked["clock_offset_s"] == pytest.approx(DEVICE_BEHIND_S, abs=1.0)
    laps = detail["tracks"][0]["laps"]
    assert len(laps) == len(LAP_TIMES)
    for lap, duration in zip(laps, LAP_TIMES):
        assert lap["avg_power_w"] == pytest.approx(5000 / duration, rel=0.06)
        assert lap["avg_heart_rate"] == pytest.approx(150, abs=1)
        assert lap["avg_cadence"] == pytest.approx(100, abs=3)

    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/evt-f/efforts")).json()
    assert efforts and efforts[0]["avg_power_w"] is not None
    total = sum(LAP_TIMES)
    expected = sum(5000 / d * d for d in LAP_TIMES) / total  # time-weighted: each lap is 5000 W·s / d * d
    assert efforts[0]["avg_power_w"] == pytest.approx(expected, rel=0.05)


async def test_a_session_without_a_recording_has_no_lap_power(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)
    detail = (await client.get(f"/athletes/{athlete_id}/sessions/evt-f")).json()
    assert detail["activities"] == []
    assert all(lap["avg_power_w"] is None for lap in detail["tracks"][0]["laps"])


async def _strava_recording_linked_to_session(db_session, athlete_id: str) -> None:
    async with db_session() as session:
        event = await session.scalar(select(TrainingEvent))
        activity = Activity(
            athlete_id=uuid.UUID(athlete_id),
            source=ActivitySource.STRAVA,
            external_id="s-1",
            start_time=SESSION_START - timedelta(minutes=2),
            elapsed_s=2400,
            training_event_id=event.id,
        )
        session.add(activity)
        await session.flush()
        seconds = list(range(2400))
        session.add(
            ActivityStream(
                activity_id=activity.id,
                sample_count=len(seconds),
                time_s=streams.pack("time_s", seconds),
                power_w=streams.pack("power_w", [321] * len(seconds)),
            )
        )
        await session.commit()


async def test_strava_power_never_reaches_a_coachs_lap_table(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)
    await _strava_recording_linked_to_session(db_session, athlete_id)

    mine = (await client.get(f"/athletes/{athlete_id}/sessions/evt-f")).json()
    assert len(mine["activities"]) == 1 and mine["tracks"][0]["laps"][5]["avg_power_w"] == pytest.approx(321)
    async with _coach_of(db_session, athlete_id) as coach:
        theirs = (await coach.get(f"/athletes/{athlete_id}/sessions/evt-f")).json()
        assert theirs["activities"] == []
        assert all(lap["avg_power_w"] is None for lap in theirs["tracks"][0]["laps"])
        efforts = (await coach.get(f"/athletes/{athlete_id}/sessions/evt-f/efforts")).json()
        assert all(e["avg_power_w"] is None for e in efforts)


async def test_coaches_cannot_link_or_unlink(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)
    activity = await _upload(client, athlete_id, _recording())
    url = f"/athletes/{athlete_id}/activities/{activity['id']}/session"
    async with _coach_of(db_session, athlete_id) as coach:
        assert (await coach.delete(url)).status_code == 403
        assert (await coach.put(url, json={"external_event_id": "evt-f"})).status_code == 403
        assert (await coach.get(url + "/suggestion")).status_code == 200


# --- training load ---------------------------------------------------------------


async def test_a_session_and_its_recording_count_once_in_the_training_load(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-05-01", "ftp_w": 250})
    await client.patch(f"/athletes/{athlete_id}/sessions/evt-f", json={"rpe": 8})
    params = {"through": "2026-06-05", "days": 3}

    rated_session_only = (await client.get(f"/athletes/{athlete_id}/training-load", params=params)).json()
    day = next(d for d in rated_session_only["days"] if d["day"] == "2026-06-05")
    assert day["tss"] > 0

    activity = await _upload(client, athlete_id, _recording())
    both = (await client.get(f"/athletes/{athlete_id}/training-load", params=params)).json()
    day_with_recording = next(d for d in both["days"] if d["day"] == "2026-06-05")
    assert day_with_recording["tss"] == pytest.approx(activity["tss"])  # the recording replaces the session's sRPE

    await client.delete(f"/athletes/{athlete_id}/activities/{activity['id']}/session")
    unlinked = (await client.get(f"/athletes/{athlete_id}/training-load", params=params)).json()
    day_unlinked = next(d for d in unlinked["days"] if d["day"] == "2026-06-05")
    assert day_unlinked["tss"] == pytest.approx(day["tss"] + activity["tss"])  # unlinked: both count


# --- account deletion ---------------------------------------------------------------


async def test_deleting_the_account_removes_linked_activities_before_their_sessions(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session)
    user_id = (await client.get("/auth/me")).json()["id"]
    await _upload(client, athlete_id, _recording())

    resp = await client.post("/auth/delete-account", json={"password": "Correcthorse123!"})

    assert resp.status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, uuid.UUID(user_id), uuid.UUID(athlete_id)) == []
        assert (await session.scalars(select(Activity))).all() == []
        assert (await session.scalars(select(TrainingEvent))).all() == []

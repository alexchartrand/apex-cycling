import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.activities.models import Activity, ActivityPowerCurve, ActivitySource, ActivityStream
from app.athletes.models import CoachAthlete, CoachAthleteStatus
from app.core.config import get_settings
from app.main import app as real_app
from tests.fit_builder import build_fit
from tests.test_account import _signup

START = datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


def _fit(seconds: int = 60, start: datetime = START, power: int = 200) -> bytes:
    return build_fit(
        start,
        [{"t": t, "power": power + t, "heart_rate": 130, "cadence": 90, "speed": 10.0, "distance": 10.0 * t}
         for t in range(seconds)],
    )  # fmt: skip


def _files(*named: tuple[str, bytes]):
    return [("files", (name, content, "application/octet-stream")) for name, content in named]


def _other_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api")


async def _athlete_id(client) -> str:
    return (await client.get("/athletes/me")).json()["id"]


async def test_upload_stores_summary_samples_and_original(client, db_session, uploads_dir):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    content = _fit(60)

    resp = await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("ride.fit", content)))

    assert resp.status_code == 200
    (result,) = resp.json()
    assert result["status"] == "created"
    activity = result["activity"]
    assert activity["source"] == "upload"
    assert activity["file_format"] == "fit"
    assert activity["has_power"] and activity["has_heart_rate"] and activity["has_cadence"]
    assert activity["elapsed_s"] == 59
    assert activity["distance_m"] == 590
    assert activity["avg_power_w"] == pytest.approx(229.5, abs=0.1)
    assert activity["start_time"].startswith("2026-06-01T07:00:00")

    async with db_session() as session:
        row = await session.get(Activity, uuid.UUID(activity["id"]))
        assert (uploads_dir / row.file_path).read_bytes() == content
        stream = await session.get(ActivityStream, row.id)
        assert stream.sample_count == 60


async def test_same_file_twice_is_a_duplicate(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    content = _fit()

    first = (await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("a.fit", content)))).json()
    again = (await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("renamed.fit", content)))).json()

    assert again[0]["status"] == "duplicate"
    assert again[0]["activity"]["id"] == first[0]["activity"]["id"]
    async with db_session() as session:
        assert len((await session.scalars(select(Activity))).all()) == 1


async def test_the_same_file_twice_in_one_request_is_stored_once(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    content = _fit()

    resp = await client.post(
        f"/athletes/{athlete_id}/activities/upload", files=_files(("a.fit", content), ("b.fit", content))
    )

    assert [r["status"] for r in resp.json()] == ["created", "duplicate"]


async def test_another_recording_of_the_same_ride_is_a_duplicate(client):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    gpx = b"""<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
      <trkpt lat="45" lon="-72"><time>2026-06-01T07:00:01Z</time></trkpt>
      <trkpt lat="45.001" lon="-72"><time>2026-06-01T07:00:59Z</time></trkpt></trkseg></trk></gpx>"""

    fit = (await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("a.fit", _fit(60))))).json()
    same = (await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("a.gpx", gpx)))).json()

    assert same[0]["status"] == "duplicate"
    assert same[0]["activity"]["id"] == fit[0]["activity"]["id"]


async def test_one_bad_file_does_not_spoil_the_others(client):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)

    resp = await client.post(
        f"/athletes/{athlete_id}/activities/upload",
        files=_files(("notes.txt", b"not an activity"), ("ride.fit", _fit()), ("bad.fit", _fit()[:50])),
    )

    results = resp.json()
    assert [r["status"] for r in results] == ["failed", "created", "failed"]
    assert "unsupported" in results[0]["error"]
    assert results[0]["activity"] is None
    assert len((await client.get(f"/athletes/{athlete_id}/activities")).json()) == 1


async def test_oversized_files_and_too_many_files(client, monkeypatch):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    monkeypatch.setattr(get_settings(), "max_activity_file_bytes", 1000)

    big = (await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("big.fit", _fit(60))))).json()
    assert big[0]["status"] == "failed" and "too large" in big[0]["error"]

    many = _files(*[(f"{i}.fit", b"x") for i in range(21)])
    assert (await client.post(f"/athletes/{athlete_id}/activities/upload", files=many)).status_code == 413


async def test_list_orders_newest_first_and_filters_by_date(client):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    for day in (1, 5, 9):
        start = datetime(2026, 6, day, 7, 0, tzinfo=timezone.utc)
        await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files((f"{day}.fit", _fit(30, start))))

    listing = (await client.get(f"/athletes/{athlete_id}/activities")).json()
    assert [a["start_time"][:10] for a in listing] == ["2026-06-09", "2026-06-05", "2026-06-01"]

    window = (
        await client.get(f"/athletes/{athlete_id}/activities", params={"start": "2026-06-02T00:00:00Z", "end": "2026-06-08T00:00:00Z"})
    ).json()
    assert [a["start_time"][:10] for a in window] == ["2026-06-05"]
    assert len((await client.get(f"/athletes/{athlete_id}/activities", params={"limit": 1, "offset": 1})).json()) == 1

    one = await client.get(f"/athletes/{athlete_id}/activities/{listing[0]['id']}")
    assert one.status_code == 200 and one.json()["id"] == listing[0]["id"]


async def test_delete_removes_rows_and_file(client, db_session, uploads_dir):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    created = (await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("a.fit", _fit())))).json()
    activity_id = created[0]["activity"]["id"]
    async with db_session() as session:
        path = (await session.get(Activity, uuid.UUID(activity_id))).file_path
        session.add(ActivityPowerCurve(activity_id=uuid.UUID(activity_id), duration_s=5, power_w=300))
        await session.commit()
    assert (uploads_dir / path).exists()

    assert (await client.delete(f"/athletes/{athlete_id}/activities/{activity_id}")).status_code == 204

    assert (await client.get(f"/athletes/{athlete_id}/activities/{activity_id}")).status_code == 404
    assert not (uploads_dir / path).exists()
    async with db_session() as session:
        for model in (Activity, ActivityStream, ActivityPowerCurve):
            assert (await session.scalars(select(model))).all() == []
    # ... and the same file can be imported again.
    again = await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("a.fit", _fit())))
    assert again.json()[0]["status"] == "created"


# --- who may do what -------------------------------------------------------


@asynccontextmanager
async def _coach_of(db_session, athlete_id: str):
    """A second signed-in user with an active coach link to the athlete."""
    async with _other_client() as coach_client:
        coach = await _signup(coach_client, "coach@example.com")
        async with db_session() as session:
            session.add(
                CoachAthlete(
                    coach_user_id=uuid.UUID(coach["id"]),
                    athlete_id=uuid.UUID(athlete_id),
                    status=CoachAthleteStatus.ACTIVE,
                )
            )
            await session.commit()
        yield coach_client


async def test_a_coach_reads_but_cannot_add_or_delete(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    created = (await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("a.fit", _fit())))).json()
    activity_id = created[0]["activity"]["id"]

    async with _coach_of(db_session, athlete_id) as coach:
        assert len((await coach.get(f"/athletes/{athlete_id}/activities")).json()) == 1
        assert (await coach.get(f"/athletes/{athlete_id}/activities/{activity_id}")).status_code == 200
        upload = await coach.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("b.fit", _fit(30, START.replace(day=9)))))
        assert upload.status_code == 403
        assert (await coach.delete(f"/athletes/{athlete_id}/activities/{activity_id}")).status_code == 403

    assert len((await client.get(f"/athletes/{athlete_id}/activities")).json()) == 1


async def test_strava_activities_are_for_their_owner_only(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    async with db_session() as session:
        for source, external_id in ((ActivitySource.STRAVA, "s1"), (ActivitySource.INTERVALS_ICU, "i1")):
            session.add(
                Activity(
                    athlete_id=uuid.UUID(athlete_id),
                    source=source,
                    external_id=external_id,
                    start_time=START,
                    elapsed_s=100,
                )
            )
        await session.commit()
        strava_id = (await session.scalar(select(Activity).where(Activity.source == ActivitySource.STRAVA))).id

    assert {a["source"] for a in (await client.get(f"/athletes/{athlete_id}/activities")).json()} == {
        "strava",
        "intervals_icu",
    }
    async with _coach_of(db_session, athlete_id) as coach:
        assert {a["source"] for a in (await coach.get(f"/athletes/{athlete_id}/activities")).json()} == {"intervals_icu"}
        assert (await coach.get(f"/athletes/{athlete_id}/activities/{strava_id}")).status_code == 404


async def test_strangers_and_signed_out_users_get_nothing(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    created = (await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("a.fit", _fit())))).json()
    activity_id = created[0]["activity"]["id"]

    async with _other_client() as stranger:
        assert (await stranger.get(f"/athletes/{athlete_id}/activities")).status_code == 401
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(f"/athletes/{athlete_id}/activities")).status_code == 403
        assert (await stranger.get(f"/athletes/{athlete_id}/activities/{activity_id}")).status_code == 403
        assert (await stranger.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("a.fit", _fit())))).status_code == 403
        assert (await stranger.delete(f"/athletes/{athlete_id}/activities/{activity_id}")).status_code == 403


async def test_a_file_stored_for_one_athlete_is_not_found_through_another(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _athlete_id(client)
    created = (await client.post(f"/athletes/{athlete_id}/activities/upload", files=_files(("a.fit", _fit())))).json()
    activity_id = created[0]["activity"]["id"]

    async with _other_client() as other:
        await _signup(other, "other@example.com")
        other_athlete = await _athlete_id(other)
        assert (await other.get(f"/athletes/{other_athlete}/activities/{activity_id}")).status_code == 404
        assert (await other.delete(f"/athletes/{other_athlete}/activities/{activity_id}")).status_code == 404

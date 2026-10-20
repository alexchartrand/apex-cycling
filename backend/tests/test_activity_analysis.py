import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.activities import downsample
from app.activities.models import Activity, ActivitySource
from app.athletes.models import CoachAthlete, CoachAthleteStatus
from app.core.config import get_settings
from app.main import app as real_app
from tests.fit_builder import build_fit
from tests.test_account import _signup

START = datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


# --- downsampling ---------------------------------------------------------------------


def test_bucket_size_keeps_the_point_count_under_the_limit():
    assert downsample.bucket_size(1000, 1200) == 1
    assert downsample.bucket_size(10_000, 1200) == 9
    assert downsample.bucket_size(10_000, 1200) * 1200 >= 10_000


def test_averaged_channels_are_smoothed_and_cumulative_ones_keep_the_last_reading():
    assert downsample.downsample("power_w", [100, 200, None, 400, 500, 600], 3) == [150.0, 500.0]
    assert downsample.downsample("time_s", [0, 1, 2, 3, 4, 5], 3) == [2, 5]
    assert downsample.downsample("distance_m", [0, 10, None, 30, 40, 50], 3) == [10, 50]


def test_gaps_stay_gaps_and_size_one_is_a_copy():
    assert downsample.downsample("heart_rate", [None, None, 120, 130], 2) == [None, 125.0]
    assert downsample.downsample("heart_rate", [1, None, 3], 1) == [1, None, 3]


# --- endpoints ---------------------------------------------------------------------------


def _fit(seconds: int = 600, power: int = 250) -> bytes:
    return build_fit(
        START, [{"t": t, "power": power, "heart_rate": 140, "cadence": 90, "speed": 10.0, "distance": 10.0 * t} for t in range(seconds)]
    )


async def _rider(client) -> str:
    await _signup(client, "rider@example.com")
    return (await client.get("/athletes/me")).json()["id"]


async def _upload(client, athlete_id, content=None) -> dict:
    resp = await client.post(
        f"/athletes/{athlete_id}/activities/upload",
        files=[("files", ("a.fit", content or _fit(), "application/octet-stream"))],
    )
    return resp.json()[0]["activity"]


@asynccontextmanager
async def _coach_of(db_session, athlete_id: str):
    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as coach_client:
        coach = await _signup(coach_client, "coach@example.com")
        async with db_session() as session:
            session.add(
                CoachAthlete(coach_user_id=uuid.UUID(coach["id"]), athlete_id=uuid.UUID(athlete_id), status=CoachAthleteStatus.ACTIVE)
            )
            await session.commit()
        yield coach_client


async def test_streams_are_thinned_to_the_requested_size(client):
    athlete_id = await _rider(client)
    activity = await _upload(client, athlete_id)

    body = (await client.get(f"/athletes/{athlete_id}/activities/{activity['id']}/streams", params={"max_points": 100})).json()

    assert body["sample_count"] == 600 and body["point_count"] == 100  # buckets of 6
    assert len(body["time_s"]) == len(body["power_w"]) == 100
    assert body["power_w"][0] == 250 and body["heart_rate"][-1] == 140
    assert body["time_s"][-1] == 599 and body["distance_m"][-1] == pytest.approx(5990)
    assert body["altitude_m"] is None  # the file has none

    full = (await client.get(f"/athletes/{athlete_id}/activities/{activity['id']}/streams")).json()
    assert full["point_count"] == 600
    assert (await client.get(f"/athletes/{athlete_id}/activities/{activity['id']}/streams", params={"max_points": 5})).status_code == 422


async def test_analysis_of_a_ride_at_ftp(client):
    athlete_id = await _rider(client)
    await client.post(
        f"/athletes/{athlete_id}/metrics",
        json={"effective_date": "2026-05-01", "ftp_w": 250, "weight_kg": 70, "max_hr": 190},
    )
    activity = await _upload(client, athlete_id)

    analysis = (await client.get(f"/athletes/{athlete_id}/activities/{activity['id']}/analysis")).json()

    assert (analysis["ftp_w"], analysis["weight_kg"], analysis["max_hr"]) == (250, 70, 190)
    assert analysis["intensity_factor"] == pytest.approx(1.0) and analysis["variability_index"] == pytest.approx(1.0)
    assert analysis["avg_power_w_per_kg"] == pytest.approx(250 / 70)
    assert analysis["work_kj"] == pytest.approx(150)
    assert analysis["power_zones"]["limits"] == pytest.approx([137.5, 187.5, 225, 262.5, 300, 375])
    assert analysis["power_zones"]["seconds"] == [0, 0, 0, 600, 0, 0, 0]  # 250 W is Coggan zone 4
    assert analysis["hr_zones"]["seconds"] == [0, 0, 600, 0, 0]  # 140 of 190 bpm: zone 3
    curve = {p["duration_s"]: p["power_w"] for p in analysis["power_curve"]}
    assert curve[1] == 250 and curve[600] == 250 and 3600 not in curve


async def test_analysis_without_physiology_or_power_says_what_it_cannot(client):
    athlete_id = await _rider(client)
    with_power = await _upload(client, athlete_id)
    analysis = (await client.get(f"/athletes/{athlete_id}/activities/{with_power['id']}/analysis")).json()
    assert analysis["ftp_w"] is None and analysis["intensity_factor"] is None
    assert analysis["power_zones"] is None and analysis["hr_zones"] is None
    assert analysis["work_kj"] == pytest.approx(150) and analysis["variability_index"] == pytest.approx(1.0)

    no_power = build_fit(START.replace(day=2), [{"t": t, "heart_rate": 120, "speed": 8.0} for t in range(120)])
    ride = await _upload(client, athlete_id, no_power)
    bare = (await client.get(f"/athletes/{athlete_id}/activities/{ride['id']}/analysis")).json()
    assert bare["work_kj"] is None and bare["power_curve"] == [] and bare["variability_index"] is None


async def test_streams_and_analysis_respect_access_and_strava(client, db_session):
    athlete_id = await _rider(client)
    activity = await _upload(client, athlete_id)
    async with db_session() as session:
        strava = Activity(
            athlete_id=uuid.UUID(athlete_id), source=ActivitySource.STRAVA, external_id="1", start_time=START.replace(day=5), elapsed_s=60
        )
        session.add(strava)
        await session.commit()
        strava_id = str(strava.id)

    assert (await client.get(f"/athletes/{athlete_id}/activities/{strava_id}/streams")).status_code == 404  # no samples stored
    async with _coach_of(db_session, athlete_id) as coach:
        assert (await coach.get(f"/athletes/{athlete_id}/activities/{activity['id']}/streams")).status_code == 200
        assert (await coach.get(f"/athletes/{athlete_id}/activities/{strava_id}/streams")).status_code == 404
        assert (await coach.get(f"/athletes/{athlete_id}/activities/{strava_id}/analysis")).status_code == 404
    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as anonymous:
        assert (await anonymous.get(f"/athletes/{athlete_id}/activities/{activity['id']}/analysis")).status_code == 401

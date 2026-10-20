"""Saved aero tests: setups kept for comparison, results computed on read."""

import io
import uuid
import zipfile

import pytest
from sqlalchemy import update

from app.activities.models import Activity, ActivitySource
from app.aero.models import AeroTest
from app.core.config import get_settings
from tests.test_account import PASSWORD, _other_client, _rows_referencing, _signup
from tests.test_activity_fusion import _coach_of
from tests.test_aero_api import CDA, CRR, _setup


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


async def _points(client, athlete_id: str) -> list[dict]:
    return (await client.post(f"/athletes/{athlete_id}/sessions/evt-aero/aero", json={})).json()["points"]


async def test_two_setups_compared_on_one_session(client, db_session):
    athlete_id = await _setup(client, db_session)
    points = await _points(client, athlete_id)
    effort = {i: [p["lap_id"] for p in points if p["effort_index"] == i and p["lap_in_effort"] > 1] for i in (1, 2, 3)}
    url = f"/athletes/{athlete_id}/aero-tests"

    resp = await client.post(
        url,
        json={
            "external_event_id": "evt-aero",
            "label": "Hoods",
            "position": "Hands on the hoods",
            "helmet": "Road",
            "lap_ids": effort[1] + effort[2],
            "crr": CRR,
        },
    )
    assert resp.status_code == 201, resp.text
    hoods = resp.json()
    assert hoods["track_name"] == "Test Track" and hoods["event_name"] == "Aero night"
    assert hoods["inputs"]["crr"] == CRR and hoods["inputs"]["rider_kg"] is None
    assert hoods["fit"]["laps_used"] == 10 and hoods["fit"]["crr_source"] == "given"
    assert hoods["fit"]["cda_m2"] == pytest.approx(CDA, abs=0.01)
    assert sum(p["used"] for p in hoods["points"]) == 10

    resp = await client.post(
        url,
        json={"external_event_id": "evt-aero", "label": "TT helmet", "helmet": "Aero", "lap_ids": effort[3], "crr": CRR},
    )
    assert resp.status_code == 201

    listed = (await client.get(url)).json()
    assert [t["label"] for t in listed] == ["Hoods", "TT helmet"]
    assert all("points" not in t for t in listed)
    assert all(t["fit"]["cda_m2"] == pytest.approx(CDA, abs=0.01) for t in listed)

    detail = (await client.get(f"{url}/{hoods['id']}")).json()
    assert detail["position"] == "Hands on the hoods" and len(detail["points"]) == 18


async def test_editing_a_test_recomputes_it(client, db_session):
    athlete_id = await _setup(client, db_session)
    url = f"/athletes/{athlete_id}/aero-tests"
    created = (await client.post(url, json={"external_event_id": "evt-aero", "label": "A", "rider_kg": 90})).json()
    assert created["lap_ids"] is None and created["fit"]["laps_used"] == 15  # the automatic pick
    test_url = f"{url}/{created['id']}"

    points = created["points"]
    picked = [p["lap_id"] for p in points if p["effort_index"] == 3][1:]
    edited = (await client.patch(test_url, json={"lap_ids": picked, "label": "B", "notes": "Windy door open"})).json()
    assert edited["label"] == "B" and edited["notes"] == "Windy door open"
    assert edited["lap_ids"] == picked and edited["fit"]["laps_used"] == 5
    assert edited["conditions"]["rider_kg"] == 90  # untouched

    back = (await client.patch(test_url, json={"rider_kg": None, "lap_ids": None})).json()
    assert back["conditions"]["rider_kg"] == 74.0 and back["fit"]["laps_used"] == 15
    assert back["label"] == "B"

    assert (await client.patch(test_url, json={"label": None})).status_code == 422
    assert (await client.patch(test_url, json={"label": ""})).status_code == 422

    assert (await client.delete(test_url)).status_code == 204
    assert (await client.get(test_url)).status_code == 404
    assert (await client.get(url)).json() == []


async def test_creating_needs_a_session_of_the_athlete(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/aero-tests"
    assert (await client.post(url, json={"external_event_id": "nope", "label": "A"})).status_code == 404
    resp = await client.post(url, json={"external_event_id": "evt-aero", "label": "A", "track_id": str(uuid.uuid4())})
    assert resp.status_code == 404
    assert (await client.post(url, json={"external_event_id": "evt-aero", "label": ""})).status_code == 422
    # No recording yet: the test is kept and says why there's no number.
    created = (await client.post(url, json={"external_event_id": "evt-aero", "label": "A"})).json()
    assert created["problem"] == "no_power" and created["fit"] is None
    assert (await client.get(f"{url}/{uuid.uuid4()}")).status_code == 404


async def test_a_coach_sees_the_tests_but_never_strava_numbers(client, db_session):
    athlete_id = await _setup(client, db_session)
    url = f"/athletes/{athlete_id}/aero-tests"
    created = (await client.post(url, json={"external_event_id": "evt-aero", "label": "A"})).json()
    async with _coach_of(db_session, athlete_id) as coach:
        theirs = (await coach.get(url)).json()
        assert [t["fit"]["cda_m2"] for t in theirs] == [pytest.approx(created["fit"]["cda_m2"])]
        # A coach may set up tests for their athlete too.
        assert (await coach.post(url, json={"external_event_id": "evt-aero", "label": "Coach's"})).status_code == 201

        async with db_session() as session:
            await session.execute(update(Activity).values(source=ActivitySource.STRAVA, external_id="s-1"))
            await session.commit()
        assert all(t["fit"] is None and t["problem"] == "no_power" for t in (await coach.get(url)).json())
        detail = (await coach.get(f"{url}/{created['id']}")).json()
        assert all(p["power_w"] is None for p in detail["points"])
    assert all(t["fit"] is not None for t in (await client.get(url)).json())


async def test_strangers_cant_reach_the_tests(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    created = (
        await client.post(f"/athletes/{athlete_id}/aero-tests", json={"external_event_id": "evt-aero", "label": "A"})
    ).json()
    async with db_session() as session:
        assert await session.get(AeroTest, uuid.UUID(created["id"])) is not None
    async with _other_client() as stranger:
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(f"/athletes/{athlete_id}/aero-tests")).status_code in (403, 404)
        resp = await stranger.delete(f"/athletes/{athlete_id}/aero-tests/{created['id']}")
        assert resp.status_code in (403, 404)


async def test_export_and_account_deletion_cover_aero_tests(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    await client.post(f"/athletes/{athlete_id}/aero-tests", json={"external_event_id": "evt-aero", "label": "Kept"})

    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    assert "Kept" in archive.read("aero_tests.csv").decode()

    user_id = uuid.UUID((await client.get("/auth/me")).json()["id"])
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, user_id, uuid.UUID(athlete_id)) == []

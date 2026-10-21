"""Bikes, gear setups and the cadence a fixed gear implies."""

import io
import uuid
import zipfile

import pytest

from app.core.config import get_settings
from tests.test_account import PASSWORD, _other_client, _rows_referencing, _signup
from tests.test_activity_fusion import _coach_of
from tests.test_aero_api import _setup


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


async def _bike_and_gear(client, athlete_id: str, **bike) -> tuple[dict, dict]:
    created = await client.post(f"/athletes/{athlete_id}/bikes", json={"name": "Track bike", **bike})
    assert created.status_code == 201, created.text
    bike = created.json()
    gear = await client.post(
        f"/athletes/{athlete_id}/bikes/{bike['id']}/gears",
        json={"chainring_teeth": 50, "cog_teeth": 15, "rollout_mm": 2100, "tire": "  Veloflex 25  "},
    )
    assert gear.status_code == 201, gear.text
    return bike, gear.json()


async def test_bike_and_gear_crud(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    bike, gear = await _bike_and_gear(client, athlete_id, weight_kg=7.4, notes="  ")
    assert bike["notes"] is None and bike["weight_kg"] == 7.4 and bike["gears"] == []
    assert gear["tire"] == "Veloflex 25"
    assert gear["ratio"] == pytest.approx(50 / 15)
    assert gear["development_m"] == pytest.approx(7.0)
    assert gear["gear_inches"] == pytest.approx(50 / 15 * 2.1 / 3.141592653589793 / 0.0254)

    resp = await client.patch(f"/athletes/{athlete_id}/gears/{gear['id']}", json={"cog_teeth": 14, "tire": None})
    assert resp.json()["cog_teeth"] == 14 and resp.json()["tire"] is None
    assert (await client.patch(f"/athletes/{athlete_id}/gears/{gear['id']}", json={"cog_teeth": None})).status_code == 422
    assert (await client.post(f"/athletes/{athlete_id}/bikes", json={"name": " "})).status_code == 422
    assert (
        await client.post(
            f"/athletes/{athlete_id}/bikes/{bike['id']}/gears",
            json={"chainring_teeth": 50, "cog_teeth": 15, "rollout_mm": 21},
        )
    ).status_code == 422

    resp = await client.patch(f"/athletes/{athlete_id}/bikes/{bike['id']}", json={"weight_kg": None, "name": "Pursuit"})
    assert resp.json()["name"] == "Pursuit" and resp.json()["weight_kg"] is None
    assert resp.json()["notes"] is None and [g["cog_teeth"] for g in resp.json()["gears"]] == [14]

    listed = (await client.get(f"/athletes/{athlete_id}/bikes")).json()
    assert [b["name"] for b in listed] == ["Pursuit"] and len(listed[0]["gears"]) == 1

    assert (await client.delete(f"/athletes/{athlete_id}/bikes/{bike['id']}")).status_code == 204
    assert (await client.get(f"/athletes/{athlete_id}/bikes")).json() == []
    assert (await client.delete(f"/athletes/{athlete_id}/bikes/{bike['id']}")).status_code == 404


async def test_session_gear_gives_lap_and_effort_cadence(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    _, gear = await _bike_and_gear(client, athlete_id)

    before = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero")).json()
    assert before["gear_setup_id"] is None
    assert all(lap["est_cadence_rpm"] is None for lap in before["tracks"][0]["laps"])

    resp = await client.put(f"/athletes/{athlete_id}/sessions/evt-aero/gear", json={"gear_setup_id": gear["id"]})
    assert resp.status_code == 204

    detail = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero")).json()
    assert detail["gear_setup_id"] == gear["id"]
    laps = detail["tracks"][0]["laps"]
    # 250 m in 20 s on a 7 m development: 12.5 / 7 * 60 rpm
    assert laps[0]["est_cadence_rpm"] == pytest.approx(12.5 / 7 * 60)
    assert laps[6]["est_cadence_rpm"] == pytest.approx(250 / 17.5 / 7 * 60)

    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero/efforts")).json()
    assert [e["gear_setup_id"] for e in efforts] == [None] * 3
    assert efforts[0]["est_cadence_rpm"] == pytest.approx(12.5 / 7 * 60)
    assert efforts[2]["est_cadence_rpm"] == pytest.approx(250 / 16 / 7 * 60)


async def test_an_effort_can_use_another_gear_than_its_session(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    bike, gear = await _bike_and_gear(client, athlete_id)
    big = (
        await client.post(
            f"/athletes/{athlete_id}/bikes/{bike['id']}/gears",
            json={"chainring_teeth": 56, "cog_teeth": 14, "rollout_mm": 2100},
        )
    ).json()
    await client.put(f"/athletes/{athlete_id}/sessions/evt-aero/gear", json={"gear_setup_id": gear["id"]})
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero/efforts")).json()
    second = efforts[1]
    url = f"/athletes/{athlete_id}/sessions/evt-aero/efforts/{second['lap_ids'][0]}/gear"

    assert (await client.put(url, json={"gear_setup_id": big["id"]})).status_code == 204
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero/efforts")).json()
    assert [e["gear_setup_id"] for e in efforts] == [None, big["id"], None]
    assert efforts[1]["est_cadence_rpm"] == pytest.approx(250 / 17.5 / 8.4 * 60)
    assert efforts[0]["est_cadence_rpm"] == pytest.approx(12.5 / 7 * 60)

    laps = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero")).json()["tracks"][0]["laps"]
    assert laps[6]["est_cadence_rpm"] == pytest.approx(250 / 17.5 / 8.4 * 60)  # follows its effort
    assert laps[0]["est_cadence_rpm"] == pytest.approx(12.5 / 7 * 60)

    # Only the lap that starts an effort takes a gear.
    other_url = f"/athletes/{athlete_id}/sessions/evt-aero/efforts/{second['lap_ids'][1]}/gear"
    assert (await client.put(other_url, json={"gear_setup_id": gear["id"]})).status_code == 404

    # Clearing the effort's gear goes back to the session's.
    assert (await client.put(url, json={"gear_setup_id": None})).status_code == 204
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero/efforts")).json()
    assert efforts[1]["gear_setup_id"] is None and efforts[1]["est_cadence_rpm"] == pytest.approx(250 / 17.5 / 7 * 60)


async def test_no_cadence_without_the_track_length(client, db_session):
    athlete_id = await _setup(client, db_session, length_m=None, upload=False)
    _, gear = await _bike_and_gear(client, athlete_id)
    await client.put(f"/athletes/{athlete_id}/sessions/evt-aero/gear", json={"gear_setup_id": gear["id"]})
    laps = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero")).json()["tracks"][0]["laps"]
    assert all(lap["est_cadence_rpm"] is None for lap in laps)


async def test_deleting_a_gear_unassigns_it(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    bike, gear = await _bike_and_gear(client, athlete_id)
    await client.put(f"/athletes/{athlete_id}/sessions/evt-aero/gear", json={"gear_setup_id": gear["id"]})
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero/efforts")).json()
    await client.put(
        f"/athletes/{athlete_id}/sessions/evt-aero/efforts/{efforts[0]['lap_ids'][0]}/gear",
        json={"gear_setup_id": gear["id"]},
    )

    assert (await client.delete(f"/athletes/{athlete_id}/gears/{gear['id']}")).status_code == 204
    assert (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero")).json()["gear_setup_id"] is None
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero/efforts")).json()
    assert efforts[0]["gear_setup_id"] is None and efforts[0]["est_cadence_rpm"] is None
    assert (await client.get(f"/athletes/{athlete_id}/bikes")).json()[0]["gears"] == []


async def test_gear_of_another_athlete_is_refused(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    async with _other_client() as other:
        await _signup(other, "other@example.com")
        other_athlete_id = (await other.get("/athletes/me")).json()["id"]
        _, theirs = await _bike_and_gear(other, other_athlete_id)
        resp = await client.put(f"/athletes/{athlete_id}/sessions/evt-aero/gear", json={"gear_setup_id": theirs["id"]})
        assert resp.status_code == 404
        assert (await client.patch(f"/athletes/{athlete_id}/gears/{theirs['id']}", json={"cog_teeth": 12})).status_code == 404
        assert (await client.delete(f"/athletes/{athlete_id}/gears/{theirs['id']}")).status_code == 404
    assert (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero")).json()["gear_setup_id"] is None


async def test_coach_can_set_gear_but_another_athlete_cannot_read_it(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    _, gear = await _bike_and_gear(client, athlete_id)
    async with _coach_of(db_session, athlete_id) as coach:
        assert (await coach.get(f"/athletes/{athlete_id}/bikes")).status_code == 200
        resp = await coach.put(f"/athletes/{athlete_id}/sessions/evt-aero/gear", json={"gear_setup_id": gear["id"]})
        assert resp.status_code == 204
    async with _other_client() as other:
        await _signup(other, "stranger@example.com")
        assert (await other.get(f"/athletes/{athlete_id}/bikes")).status_code in (403, 404)


async def test_the_bike_weight_is_the_aero_default(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    bike, gear = await _bike_and_gear(client, athlete_id, weight_kg=7.0)
    url = f"/athletes/{athlete_id}/sessions/evt-aero/aero"
    assert (await client.post(url, json={})).json()["conditions"]["bike_kg"] == 8.0

    await client.put(f"/athletes/{athlete_id}/sessions/evt-aero/gear", json={"gear_setup_id": gear["id"]})
    assert (await client.post(url, json={})).json()["conditions"]["bike_kg"] == 7.0
    assert (await client.post(url, json={"bike_kg": 9})).json()["conditions"]["bike_kg"] == 9.0

    await client.patch(f"/athletes/{athlete_id}/bikes/{bike['id']}", json={"weight_kg": None})
    assert (await client.post(url, json={})).json()["conditions"]["bike_kg"] == 8.0


async def test_export_and_account_deletion_cover_equipment(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    _, gear = await _bike_and_gear(client, athlete_id, name="Kept bike")
    await client.put(f"/athletes/{athlete_id}/sessions/evt-aero/gear", json={"gear_setup_id": gear["id"]})
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero/efforts")).json()
    await client.put(
        f"/athletes/{athlete_id}/sessions/evt-aero/efforts/{efforts[0]['lap_ids'][0]}/gear",
        json={"gear_setup_id": gear["id"]},
    )

    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    assert "Kept bike" in archive.read("bikes.csv").decode()
    assert "2100" in archive.read("gear_setups.csv").decode()

    user_id = uuid.UUID((await client.get("/auth/me")).json()["id"])
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, user_id, uuid.UUID(athlete_id)) == []

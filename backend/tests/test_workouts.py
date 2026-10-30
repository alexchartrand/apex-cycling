"""The workout library: my workouts, my coaches' libraries, duplicating."""

import io
import uuid
import zipfile

import pytest
from sqlalchemy import select

from app.workouts.models import Workout
from tests.test_account import PASSWORD, _other_client, _rows_referencing, _signup
from tests.test_activity_fusion import _coach_of
from tests.test_aero_api import _setup


@pytest.fixture(autouse=True)
def _no_presets(monkeypatch):
    """The library without the built-in workouts (`test_workout_presets.py`)."""
    monkeypatch.setattr("app.workouts.service.presets", lambda: {})


def _workout(**over) -> dict:
    return {
        "name": "  Flying 200s  ",
        "description": "  Full recovery  ",
        "tags": ["Sprint", " sprint ", "Track", ""],
        "steps": [
            {"kind": "warmup", "duration_s": 900, "power": {"unit": "ftp_pct", "low": 55, "high": 65}},
            {
                "type": "repeat",
                "count": 4,
                "steps": [
                    {"event_key": "f200", "start_type": "flying", "laps": 3, "gear": {"chainring_teeth": 50, "cog_teeth": 14}},
                    {"kind": "recovery", "laps": 6, "rpe": 2},
                ],
            },
            {"kind": "cooldown", "duration_s": 600},
        ],
        **over,
    }


async def test_create_read_edit_and_delete_my_workout(client, db_session):
    await _setup(client, db_session, upload=False)

    created = await client.post("/workouts", json=_workout())
    assert created.status_code == 201, created.text
    workout = created.json()
    assert workout["name"] == "Flying 200s" and workout["description"] == "Full recovery"
    assert workout["tags"] == ["sprint", "track"]
    assert workout["is_track"] is True and workout["can_edit"] is True and workout["owner_name"]
    assert workout["estimate"]["open_steps"] == 0
    assert len(workout["estimate"]["segments"]) == 1 + 4 * 2 + 1
    assert workout["duration_s"] == workout["estimate"]["duration_s"] > 1500
    repeat = workout["steps"][1]
    assert repeat["type"] == "repeat" and repeat["steps"][0]["gear"] == {"chainring_teeth": 50, "cog_teeth": 14}

    url = f"/workouts/{workout['id']}"
    assert (await client.get(url)).json()["steps"] == workout["steps"]
    edited = (await client.patch(url, json={"name": "Flying 200s ×4", "tags": [], "description": None})).json()
    assert edited["name"] == "Flying 200s ×4" and edited["tags"] == [] and edited["description"] is None
    assert edited["steps"] == workout["steps"]
    steps_only = (await client.patch(url, json={"steps": [{"duration_s": 3600, "power": {"unit": "ftp_pct", "low": 100}}]})).json()
    assert steps_only["is_track"] is False and steps_only["tss"] == 100

    for bad in ({"name": None}, {"steps": []}, {"name": "  "}, {"tags": ["x" * 31]}):
        assert (await client.patch(url, json=bad)).status_code == 422, bad
    assert (await client.patch(f"/workouts/{uuid.uuid4()}", json={"name": "x"})).status_code == 404

    assert (await client.delete(url)).status_code == 204
    assert (await client.get(url)).status_code == 404


async def test_a_workout_is_validated(client, db_session):
    await _setup(client, db_session, upload=False)
    bad = [
        _workout(name=" "),
        _workout(steps=[]),
        _workout(steps=[{"duration_s": 60, "distance_m": 500}]),
        _workout(steps=[{"type": "lap"}]),
        _workout(tags=[str(i) for i in range(11)]),
    ]
    for body in bad:
        assert (await client.post("/workouts", json=body)).status_code == 422, body


async def test_the_estimate_endpoint_stores_nothing(client, db_session):
    await _setup(client, db_session, upload=False)
    body = {"steps": [{"laps": 4, "kind": "recovery"}, {"duration_s": 600, "power": {"unit": "watts", "low": 300}}], "ftp_w": 300, "track_length_m": 200}
    result = await client.post("/workouts/estimate", json=body)
    assert result.status_code == 200, result.text
    assert result.json()["duration_s"] == 800 / 10 + 600
    assert result.json()["tss"] == round(600 / 3600 * 100, 1)
    assert (await client.get("/workouts")).json() == []


async def test_athletes_browse_their_coaches_library_but_only_owners_edit(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    mine = (await client.post("/workouts", json=_workout(name="Mine", tags=["endurance"], steps=[{"duration_s": 3600}]))).json()

    async with _coach_of(db_session, athlete_id) as coach:
        coach_workout = (await coach.post("/workouts", json=_workout(name="Coach's kilo"))).json()
        # The coach doesn't see the athlete's personal library.
        assert [w["name"] for w in (await coach.get("/workouts")).json()] == ["Coach's kilo"]
        assert (await coach.get(f"/workouts/{mine['id']}")).status_code == 404

        listed = (await client.get("/workouts")).json()
        assert [(w["name"], w["can_edit"]) for w in listed] == [("Coach's kilo", False), ("Mine", True)]
        assert listed[0]["owner_name"] == "Rider"
        assert [w["name"] for w in (await client.get("/workouts", params={"source": "mine"})).json()] == ["Mine"]
        assert [w["name"] for w in (await client.get("/workouts", params={"source": "coach"})).json()] == ["Coach's kilo"]
        assert [w["name"] for w in (await client.get("/workouts", params={"track": True})).json()] == ["Coach's kilo"]
        assert [w["name"] for w in (await client.get("/workouts", params={"tag": "ENDURANCE"})).json()] == ["Mine"]
        assert [w["name"] for w in (await client.get("/workouts", params={"q": "kilo"})).json()] == ["Coach's kilo"]
        # The coach's is about 39 min, mine an hour.
        assert [w["name"] for w in (await client.get("/workouts", params={"min_duration_s": 3000})).json()] == ["Mine"]
        assert [w["name"] for w in (await client.get("/workouts", params={"max_duration_s": 3000})).json()] == [
            "Coach's kilo"
        ]

        url = f"/workouts/{coach_workout['id']}"
        assert (await client.get(url)).status_code == 200
        assert (await client.patch(url, json={"name": "Hijack"})).status_code == 403
        assert (await client.delete(url)).status_code == 403

        copy = await client.post(f"{url}/duplicate")
        assert copy.status_code == 201
        assert copy.json()["can_edit"] is True and copy.json()["id"] != coach_workout["id"]
        assert copy.json()["steps"] == coach_workout["steps"]
        assert (await client.patch(f"/workouts/{copy.json()['id']}", json={"name": "My kilo"})).status_code == 200

    async with _other_client() as stranger:
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get("/workouts")).json() == []
        assert (await stranger.get(url)).status_code == 404
        assert (await stranger.post(f"{url}/duplicate")).status_code == 404
        assert (await stranger.patch(url, json={"name": "x"})).status_code == 404


async def test_a_revoked_coach_library_disappears(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    async with _coach_of(db_session, athlete_id) as coach:
        coach_workout = (await coach.post("/workouts", json=_workout())).json()
        links = (await client.get("/coach-links/coaches")).json()
        assert (await client.post(f"/coach-links/{links[0]['id']}/revoke")).status_code == 204
        assert (await client.get("/workouts")).json() == []
        assert (await client.get(f"/workouts/{coach_workout['id']}")).status_code == 404


async def test_export_and_account_deletion_cover_workouts(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    await client.post("/workouts", json=_workout(name="Kept workout"))

    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    assert "Kept workout" in archive.read("workouts.csv").decode()

    user_id = uuid.UUID((await client.get("/auth/me")).json()["id"])
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, user_id, uuid.UUID(athlete_id)) == []
        assert (await session.scalars(select(Workout))).all() == []

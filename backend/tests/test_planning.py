"""Planned sessions: the coach plans, the athlete marks done or links the ride."""

import io
import uuid
import zipfile
from datetime import date, timedelta

from sqlalchemy import select

from app.auth.models import User
from app.planning.models import PlannedSession
from app.workouts.presets import presets
from tests.test_account import PASSWORD, _other_client, _rows_referencing, _signup
from tests.test_activity_fusion import _coach_of
from tests.test_aero_api import _setup


def _plan(**over) -> dict:
    return {
        "planned_date": (date.today() + timedelta(days=3)).isoformat(),
        "title": "Kilo openers",
        "description": "  Full recovery between efforts  ",
        "targets": [
            {"label": "Standing start", "reps": 3, "event_key": "500m", "start_type": "standing", "target_time_ms": 34_000},
            {"label": "Tempo", "reps": 4},
        ],
        **over,
    }


async def test_the_athlete_plans_marks_done_and_unlinks(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"

    created = await client.post(url, json=_plan())
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["title"] == "Kilo openers" and plan["description"] == "Full recovery between efforts"
    assert plan["status"] == "planned" and plan["session"] is None
    assert plan["can_edit"] and plan["can_mark"] and plan["created_by_name"]
    assert plan["targets"][0] == {
        "label": "Standing start",
        "reps": 3,
        "event_key": "500m",
        "start_type": "standing",
        "target_time_ms": 34_000,
        "gear_setup_id": None,
        "gear_label": None,
    }
    assert plan["targets"][1] == {
        "label": "Tempo",
        "reps": 4,
        "event_key": None,
        "start_type": None,
        "target_time_ms": None,
        "gear_setup_id": None,
        "gear_label": None,
    }

    done = (await client.patch(f"{url}/{plan['id']}", json={"status": "done"})).json()
    assert done["status"] == "done" and done["session"] is None
    skipped = (await client.patch(f"{url}/{plan['id']}", json={"status": "skipped"})).json()
    assert skipped["status"] == "skipped"

    linked = await client.put(f"{url}/{plan['id']}/session", json={"external_event_id": "evt-aero"})
    assert linked.status_code == 200, linked.text
    assert linked.json()["status"] == "done"
    assert linked.json()["session"] == {
        "external_event_id": "evt-aero",
        "event_name": "Aero night",
        "event_date": "2026-06-12",
    }
    # Not done any more means not linked either.
    reset = (await client.patch(f"{url}/{plan['id']}", json={"status": "planned"})).json()
    assert reset["status"] == "planned" and reset["session"] is None

    await client.put(f"{url}/{plan['id']}/session", json={"external_event_id": "evt-aero"})
    unlinked = (await client.delete(f"{url}/{plan['id']}/session")).json()
    assert unlinked["status"] == "planned" and unlinked["session"] is None

    assert (await client.put(f"{url}/{plan['id']}/session", json={"external_event_id": "nope"})).status_code == 404


async def test_a_plan_is_validated(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    bad = [
        _plan(title="  "),
        _plan(planned_date="soon"),
        _plan(targets=[{"label": "x", "reps": 0}]),
        _plan(targets=[{"label": "x", "event_key": "marathon"}]),
        _plan(targets=[{"label": "x", "event_key": "f200", "start_type": "standing"}]),
        _plan(targets=[{"label": "x", "target_time_ms": 30_000}]),  # a time goes with an event
        _plan(targets=[{"label": "x", "event_key": "500m", "target_time_ms": 0}]),
        _plan(targets=[{"label": " "}]),
    ]
    for body in bad:
        assert (await client.post(url, json=body)).status_code == 422, body
    ok = await client.post(url, json=_plan(targets=[], description=None))
    assert ok.status_code == 201 and ok.json()["targets"] == []


async def test_listing_by_date_range_and_editing_content(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    today = date.today()
    for days, title in ((10, "Later"), (-5, "Earlier"), (2, "Soon")):
        await client.post(url, json=_plan(title=title, planned_date=(today + timedelta(days=days)).isoformat(), targets=[]))

    assert [p["title"] for p in (await client.get(url)).json()] == ["Earlier", "Soon", "Later"]
    window = (await client.get(url, params={"from": today.isoformat(), "to": (today + timedelta(days=5)).isoformat()})).json()
    assert [p["title"] for p in window] == ["Soon"]

    plan = window[0]
    edited = (
        await client.patch(
            f"{url}/{plan['id']}",
            json={"title": "Soon, shorter", "description": None, "targets": [{"label": "One kilo", "event_key": "1km"}]},
        )
    ).json()
    assert edited["title"] == "Soon, shorter" and edited["description"] is None
    assert [t["label"] for t in edited["targets"]] == ["One kilo"]
    assert (await client.patch(f"{url}/{plan['id']}", json={"title": None})).status_code == 422
    assert (await client.patch(f"{url}/{uuid.uuid4()}", json={"title": "x"})).status_code == 404

    assert (await client.delete(f"{url}/{plan['id']}")).status_code == 204
    assert (await client.delete(f"{url}/{plan['id']}")).status_code == 404


async def test_the_coach_plans_but_only_the_athlete_marks_it(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    async with _coach_of(db_session, athlete_id) as coach:
        created = await coach.post(url, json=_plan())
        assert created.status_code == 201
        plan = created.json()
        assert plan["can_edit"] is True and plan["can_mark"] is False

        # The coach edits their own plan but can't say it was ridden.
        assert (await coach.patch(f"{url}/{plan['id']}", json={"title": "Kilo openers v2"})).status_code == 200
        assert (await coach.patch(f"{url}/{plan['id']}", json={"status": "done"})).status_code == 403
        assert (await coach.put(f"{url}/{plan['id']}/session", json={"external_event_id": "evt-aero"})).status_code == 403
        assert (await coach.delete(f"{url}/{plan['id']}/session")).status_code == 403

        mine = (await client.get(url)).json()[0]
        assert mine["title"] == "Kilo openers v2" and mine["can_edit"] and mine["can_mark"]
        assert mine["created_by_name"] == "Rider"  # the coach's own profile name (the signup helper's)

        # The athlete's own plan is not the coach's to edit or delete.
        own = (await client.post(url, json=_plan(title="Mine"))).json()
        assert (await coach.get(url)).json()[1]["can_edit"] is False
        assert (await coach.patch(f"{url}/{own['id']}", json={"title": "Hijack"})).status_code == 403
        assert (await coach.delete(f"{url}/{own['id']}")).status_code == 403

        # But the athlete can drop the coach's plan.
        assert (await client.delete(f"{url}/{plan['id']}")).status_code == 204


async def test_a_planned_effort_names_one_of_the_athletes_gears(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    bike = (await client.post(f"/athletes/{athlete_id}/bikes", json={"name": "Track bike"})).json()
    gear = (
        await client.post(
            f"/athletes/{athlete_id}/bikes/{bike['id']}/gears",
            json={"chainring_teeth": 50, "cog_teeth": 15, "rollout_mm": 2100},
        )
    ).json()

    async with _coach_of(db_session, athlete_id) as coach:  # a coach plans in the athlete's gear
        created = await coach.post(url, json=_plan(targets=[{"label": "Flying 200", "gear_setup_id": gear["id"]}]))
        assert created.status_code == 201, created.text
        target = created.json()["targets"][0]
        assert target["gear_setup_id"] == gear["id"] and target["gear_label"] == "Track bike · 50×15"

    async with _other_client() as other:
        await _signup(other, "other@example.com")
        theirs_athlete = (await other.get("/athletes/me")).json()["id"]
        their_bike = (await other.post(f"/athletes/{theirs_athlete}/bikes", json={"name": "Theirs"})).json()
        theirs = (
            await other.post(
                f"/athletes/{theirs_athlete}/bikes/{their_bike['id']}/gears",
                json={"chainring_teeth": 52, "cog_teeth": 14, "rollout_mm": 2100},
            )
        ).json()
    plan = created.json()
    refused = await client.patch(f"{url}/{plan['id']}", json={"targets": [{"label": "x", "gear_setup_id": theirs["id"]}]})
    assert refused.status_code == 404
    assert (await client.post(url, json=_plan(targets=[{"label": "x", "gear_setup_id": theirs["id"]}]))).status_code == 404

    # A deleted gear just drops out of the plan.
    assert (await client.delete(f"/athletes/{athlete_id}/gears/{gear['id']}")).status_code == 204
    target = (await client.get(url)).json()[0]["targets"][0]
    assert target["gear_setup_id"] is None and target["gear_label"] is None and target["label"] == "Flying 200"


async def test_strangers_cant_reach_the_plan(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    plan = (await client.post(url, json=_plan())).json()
    async with _other_client() as stranger:
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(url)).status_code in (403, 404)
        assert (await stranger.post(url, json=_plan())).status_code in (403, 404)
        mine = (await stranger.get("/athletes/me")).json()["id"]
        # A plan id only works through its own athlete.
        assert (await stranger.patch(f"/athletes/{mine}/planned-sessions/{plan['id']}", json={"title": "x"})).status_code == 404
        assert (await stranger.put(f"/athletes/{mine}/planned-sessions/{plan['id']}/session", json={"external_event_id": "e"})).status_code == 404


async def test_a_coach_deleting_their_account_leaves_the_plan(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    async with _coach_of(db_session, athlete_id) as coach:
        plan = (await coach.post(url, json=_plan())).json()
        assert (await coach.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204

    after = (await client.get(url)).json()
    assert [p["id"] for p in after] == [plan["id"]]
    assert after[0]["created_by_name"] is None and after[0]["can_edit"] is True  # the athlete's side still edits
    async with db_session() as session:
        row = await session.get(PlannedSession, uuid.UUID(plan["id"]))
        assert row.created_by_user_id is None
        assert (await session.scalar(select(User).where(User.email == "coach@example.com"))) is None


async def test_export_and_account_deletion_cover_plans(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    plan = (await client.post(url, json=_plan(title="Kept plan"))).json()
    await client.put(f"{url}/{plan['id']}/session", json={"external_event_id": "evt-aero"})  # points at a session

    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    assert "Kept plan" in archive.read("planned_sessions.csv").decode()

    user_id = uuid.UUID((await client.get("/auth/me")).json()["id"])
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, user_id, uuid.UUID(athlete_id)) == []


# --- scheduling a workout --------------------------------------------------------

STEPS = [
    {"kind": "warmup", "duration_s": 600, "power": {"unit": "ftp_pct", "low": 60}},
    {"label": "Flying 200", "event_key": "f200", "gear": {"chainring_teeth": 50, "cog_teeth": 15}},
    {"kind": "work", "duration_s": 600, "power": {"unit": "watts", "low": 300}},
]


async def test_scheduling_a_workout_keeps_a_copy(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    workout = (await client.post("/workouts", json={"name": "Openers", "steps": STEPS})).json()

    created = await client.post(url, json=_plan(targets=[], workout=STEPS, source_workout_id=workout["id"]))
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["source_workout_id"] == workout["id"]
    assert [s["label"] for s in plan["workout"]] == [None, "Flying 200", None]
    estimate = plan["workout_estimate"]
    assert estimate["duration_s"] > 1200 and len(estimate["segments"]) == 3
    # No FTP yet: the watt step counts as unrated.
    assert estimate["unrated_s"] > 600

    # Editing the library workout never rewrites the plan.
    await client.patch(f"/workouts/{workout['id']}", json={"steps": [{"duration_s": 60}]})
    assert (await client.get(url)).json()[0]["workout"] == plan["workout"]

    # The plan's own copy can be adapted, or dropped (and its source with it).
    edited = (await client.patch(f"{url}/{plan['id']}", json={"workout": STEPS[:1]})).json()
    assert len(edited["workout"]) == 1 and edited["source_workout_id"] == workout["id"]
    cleared = (await client.patch(f"{url}/{plan['id']}", json={"workout": None})).json()
    assert cleared["workout"] is None and cleared["workout_estimate"] is None and cleared["source_workout_id"] is None

    # A deleted library workout stops being offered as the source.
    again = (await client.post(url, json=_plan(targets=[], workout=STEPS, source_workout_id=workout["id"]))).json()
    await client.delete(f"/workouts/{workout['id']}")
    assert next(p for p in (await client.get(url)).json() if p["id"] == again["id"])["source_workout_id"] is None
    async with db_session() as session:
        assert (await session.get(PlannedSession, uuid.UUID(again["id"]))).source_workout_id is None


async def test_the_estimate_uses_the_ftp_on_the_planned_day(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-01-01", "ftp_w": 300})
    plan = (await client.post(url, json=_plan(targets=[], workout=STEPS[2:]))).json()
    # 10 min at 300 W on a 300 W FTP: IF 1, TSS 100/6.
    assert plan["workout_estimate"]["unrated_s"] == 0
    assert plan["workout_estimate"]["tss"] == round(100 / 6, 1)


async def test_a_workout_gear_is_matched_to_the_athletes_bikes(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    plan = (await client.post(url, json=_plan(targets=[], workout=STEPS))).json()
    assert plan["workout_gears"] == []  # no bike with that gear yet

    bike = (await client.post(f"/athletes/{athlete_id}/bikes", json={"name": "Track bike"})).json()
    gear = (
        await client.post(
            f"/athletes/{athlete_id}/bikes/{bike['id']}/gears",
            json={"chainring_teeth": 50, "cog_teeth": 15, "rollout_mm": 2100},
        )
    ).json()
    await client.post(
        f"/athletes/{athlete_id}/bikes/{bike['id']}/gears",
        json={"chainring_teeth": 48, "cog_teeth": 15, "rollout_mm": 2100},
    )
    assert (await client.get(url)).json()[0]["workout_gears"] == [
        {"chainring_teeth": 50, "cog_teeth": 15, "gear_setup_id": gear["id"], "label": "Track bike · 50×15"}
    ]


async def test_a_plan_names_only_a_workout_the_planner_can_see(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    async with _other_client() as stranger:
        await _signup(stranger, "stranger@example.com")
        theirs = (await stranger.post("/workouts", json={"name": "Secret", "steps": STEPS})).json()
    body = _plan(targets=[], workout=STEPS, source_workout_id=theirs["id"])
    assert (await client.post(url, json=body)).status_code == 404
    plan = (await client.post(url, json=_plan(targets=[], workout=STEPS))).json()
    assert (await client.patch(f"{url}/{plan['id']}", json={"source_workout_id": theirs["id"]})).status_code == 404

    # A preset is everyone's.
    preset_id = str(next(iter(presets())))
    ok = await client.post(url, json=_plan(targets=[], workout=STEPS, source_workout_id=preset_id))
    assert ok.status_code == 201 and ok.json()["source_workout_id"] == preset_id

    # The steps are checked like a library workout's.
    assert (await client.post(url, json=_plan(workout=[]))).status_code == 422
    assert (await client.post(url, json=_plan(workout=[{"duration_s": 60, "laps": 2}]))).status_code == 422


async def test_the_coach_schedules_from_their_library(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    async with _coach_of(db_session, athlete_id) as coach:
        workout = (await coach.post("/workouts", json={"name": "Coach openers", "steps": STEPS})).json()
        created = await coach.post(url, json=_plan(targets=[], workout=STEPS, source_workout_id=workout["id"]))
        assert created.status_code == 201, created.text
        # The athlete sees the coach's library, so the source stays linked for them too.
        assert (await client.get(url)).json()[0]["source_workout_id"] == workout["id"]
        assert (await coach.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204

    # The coach is gone with their library; the athlete keeps the copy.
    kept = (await client.get(url)).json()[0]
    assert kept["workout"] is not None and kept["source_workout_id"] is None
    async with db_session() as session:
        assert (await session.get(PlannedSession, uuid.UUID(kept["id"]))).source_workout_id is None

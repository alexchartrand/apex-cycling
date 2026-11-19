"""Training plans: one sport, one goal, phases; the athlete, a coach or the AI
writes them; several may run at once; deleting one deletes only what is
still to ride."""

import io
import uuid
import zipfile
from datetime import date, timedelta

from sqlalchemy import select

from app.planning.models import IntervalsPlanEvent, PlannedSession
from app.training_plans.models import TrainingPlan
from app.training_plans.phases import current_phase, plan_state, suggest_phases
from app.training_plans.progress import SessionFacts, summarize
from tests.test_account import PASSWORD, _other_client, _rows_referencing, _signup
from tests.test_activity_fusion import _coach_of
from tests.test_aero_api import _setup

STEPS = [{"kind": "work", "duration_s": 3600, "power": {"unit": "ftp_pct", "low": 70}}]


def _day(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _training_plan(**over) -> dict:
    return {
        "name": "Kilo season",
        "sport": "track_cycling",
        "start_date": _day(-14),
        "end_date": _day(60),
        "goal_text": "  Sub 1:10 kilo  ",
        "goal_date": _day(60),
        "hours_per_week": 8,
        "phases": [
            {"kind": "build", "start": _day(20), "end": _day(50)},
            {"kind": "base", "start": _day(-14), "end": _day(19), "focus": "Aerobic volume"},
        ],
        **over,
    }


def _session(days: int, title: str, plan_id: str | None, **over) -> dict:
    return {"planned_date": _day(days), "title": title, "workout": STEPS, "training_plan_id": plan_id, **over}


# --- pure rules --------------------------------------------------------------------


def test_suggested_phases_end_with_the_taper_and_race():
    start = date(2027, 1, 4)  # a Monday
    phases = suggest_phases(start, start + timedelta(days=12 * 7 - 1), "A")
    assert [p.kind for p in phases] == ["base", "build", "peak", "taper", "race"]
    assert phases[0].start == start and phases[-1].start == phases[-1].end == start + timedelta(days=83)
    assert (phases[-1].start - phases[-2].start).days == 10  # an A race tapers 10 days
    for before, after in zip(phases, phases[1:]):
        assert after.start == before.end + timedelta(days=1)
    assert (phases[1].start - phases[0].start).days % 7 == 0  # whole weeks

    assert [p.kind for p in suggest_phases(start, start + timedelta(days=13))] == ["build"]
    assert [p.kind for p in suggest_phases(start, start + timedelta(days=20), "C")] == ["build", "race"]
    no_race = suggest_phases(start, start + timedelta(days=55))
    assert [p.kind for p in no_race] == ["base", "build", "peak"]
    assert current_phase(no_race, start + timedelta(days=55)) == 2
    assert current_phase(no_race, start - timedelta(days=1)) is None
    assert plan_state(start, start, start - timedelta(days=1)) == "upcoming"
    assert plan_state(start, start, start + timedelta(days=1)) == "finished"


def test_progress_counts_and_weeks():
    today = date(2027, 1, 13)  # a Wednesday
    monday = date(2027, 1, 11)
    facts = [
        SessionFacts(monday, "done", planned_s=3600, planned_tss=50, done_s=3000, done_tss=40),
        SessionFacts(monday + timedelta(days=1), "planned", planned_s=1800, planned_tss=20),  # missed
        SessionFacts(monday + timedelta(days=1), "skipped", planned_s=1800),
        SessionFacts(today, "planned", planned_s=3600),
        SessionFacts(today + timedelta(days=7), "done", done_s=600),  # done ahead
    ]
    progress = summarize(facts, today)
    assert (progress.done, progress.skipped, progress.missed, progress.upcoming) == (2, 1, 1, 1)
    assert progress.compliance == round(2 / 4, 3)
    first, second = progress.weeks
    assert first.week_start == monday and (first.sessions, first.done_sessions) == (3, 1)
    assert first.planned_s == 9000 and first.planned_tss == 70 and (first.done_s, first.done_tss) == (3000, 40)
    assert second.done_s == 600 and second.done_tss is None
    assert summarize([], today).compliance is None


# --- the API ----------------------------------------------------------------------


async def test_the_athlete_makes_a_plan_and_its_sessions(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/training-plans"
    created = await client.post(url, json=_training_plan())
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["goal_text"] == "Sub 1:10 kilo" and plan["author"] == "athlete" and plan["can_edit"]
    assert [p["kind"] for p in plan["phases"]] == ["base", "build"]  # sorted
    assert plan["current_phase"] == 0 and plan["state"] == "active"
    assert plan["progress"]["upcoming"] == 0 and plan["progress"]["compliance"] is None

    sessions = f"/athletes/{athlete_id}/planned-sessions"
    made = await client.post(sessions, json=_session(2, "Openers", plan["id"]))
    assert made.status_code == 201, made.text
    assert made.json()["training_plan_name"] == "Kilo season"
    old = (await client.post(sessions, json=_session(-3, "Done ride", plan["id"]))).json()
    await client.patch(f"{sessions}/{old['id']}", json={"status": "done"})
    await client.post(sessions, json=_session(-2, "Missed", plan["id"]))
    await client.post(sessions, json=_session(1, "Outside the plan", None))

    plan = (await client.get(f"{url}/{plan['id']}")).json()
    progress = plan["progress"]
    assert (progress["done"], progress["missed"], progress["upcoming"]) == (1, 1, 1)
    assert sum(w["planned_s"] for w in progress["weeks"]) == 3 * 3600
    only = await client.get(sessions, params={"training_plan_id": plan["id"]})
    assert sorted(s["title"] for s in only.json()) == ["Done ride", "Missed", "Openers"]

    # A session leaves its plan with a null id; another athlete's plan is refused.
    detached = await client.patch(f"{sessions}/{made.json()['id']}", json={"training_plan_id": None})
    assert detached.json()["training_plan_id"] is None
    assert (await client.post(sessions, json=_session(1, "x", str(uuid.uuid4())))).status_code == 404

    renamed = await client.patch(f"{url}/{plan['id']}", json={"name": "Kilo 2027", "hours_per_week": None})
    assert renamed.status_code == 200, renamed.text
    assert (renamed.json()["name"], renamed.json()["hours_per_week"]) == ("Kilo 2027", None)
    # A change is checked against the whole plan.
    assert (await client.patch(f"{url}/{plan['id']}", json={"end_date": _day(10)})).status_code == 422


async def test_a_plan_is_validated(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/training-plans"
    bad = [
        _training_plan(name=" "),
        _training_plan(sport="running"),
        _training_plan(end_date=_day(-20)),
        _training_plan(end_date=_day(400)),
        _training_plan(goal_date=_day(90)),
        _training_plan(phases=[{"kind": "base", "start": _day(-14), "end": _day(10)}, {"kind": "build", "start": _day(10), "end": _day(20)}]),
        _training_plan(phases=[{"kind": "base", "start": _day(-20), "end": _day(10)}]),
        _training_plan(phases=[{"kind": "base", "start": _day(5), "end": _day(1)}]),
    ]
    for body in bad:
        assert (await client.post(url, json=body)).status_code == 422, body
    goal = await client.post(
        f"/athletes/{athlete_id}/goals",
        json={"event_key": "1km", "start_type": "standing", "target_time_ms": 70_000, "target_date": _day(60)},
    )
    assert goal.status_code == 201, goal.text
    goal_id = goal.json()["id"]
    # A time goal is a track event: not for a road plan.
    assert (await client.post(url, json=_training_plan(sport="cycling", goal_id=goal_id))).status_code == 422
    assert (await client.post(url, json=_training_plan(goal_id=str(uuid.uuid4())))).status_code == 404
    race = await client.post(f"/athletes/{athlete_id}/competitions", json={"name": "Provinciaux", "competition_date": _day(60)})
    made = await client.post(url, json=_training_plan(goal_id=goal_id, competition_id=race.json()["id"]))
    assert made.status_code == 201, made.text
    assert made.json()["goal"]["id"] == goal_id and made.json()["race"]["name"] == "Provinciaux"

    # Deleting the goal or the race leaves the plan without it.
    assert (await client.delete(f"/athletes/{athlete_id}/goals/{goal_id}")).status_code == 204
    assert (await client.delete(f"/athletes/{athlete_id}/competitions/{race.json()['id']}")).status_code == 204
    plan = (await client.get(f"{url}/{made.json()['id']}")).json()
    assert plan["goal"] is None and plan["race"] is None

    suggested = await client.post(f"{url}/suggest-phases", json={"start_date": _day(0), "end_date": _day(83), "race_priority": "B"})
    assert [p["kind"] for p in suggested.json()] == ["base", "build", "peak", "taper", "race"]


async def test_two_plans_run_at_once_and_deleting_one_keeps_its_history(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/training-plans"
    sessions = f"/athletes/{athlete_id}/planned-sessions"
    track = (await client.post(url, json=_training_plan())).json()
    road = (await client.post(url, json=_training_plan(name="Gran fondo", sport="cycling", goal_text="Finish"))).json()
    assert {p["name"] for p in (await client.get(url)).json()} == {"Kilo season", "Gran fondo"}

    done = (await client.post(sessions, json=_session(-3, "Done", track["id"]))).json()
    await client.patch(f"{sessions}/{done['id']}", json={"status": "done"})
    await client.post(sessions, json=_session(-1, "Missed", track["id"]))
    await client.post(sessions, json=_session(0, "Today", track["id"]))
    await client.post(sessions, json=_session(5, "Later", track["id"]))
    await client.post(sessions, json=_session(5, "Road ride", road["id"]))

    assert (await client.delete(f"{url}/{track['id']}")).status_code == 204
    left = {s["title"]: s["training_plan_id"] for s in (await client.get(sessions)).json()}
    assert left == {"Done": None, "Missed": None, "Road ride": road["id"]}
    assert (await client.get(f"{url}/{track['id']}")).status_code == 404
    async with db_session() as session:
        # The deleted sessions' Intervals.icu rows wait for the push to remove them (none here: push is off).
        assert (await session.scalars(select(IntervalsPlanEvent))).all() == []
        assert len((await session.scalars(select(TrainingPlan))).all()) == 1


async def test_who_edits_a_plan(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/training-plans"
    own = (await client.post(url, json=_training_plan(name="Mine"))).json()
    async with db_session() as session:
        ai = TrainingPlan(
            athlete_id=uuid.UUID(athlete_id), name="AI plan", sport="cycling", start_date=date.today(),
            end_date=date.today() + timedelta(days=30), created_by_ai=True,
        )
        session.add(ai)
        await session.commit()
        ai_id = str(ai.id)

    async with _coach_of(db_session, athlete_id) as coach:
        coachs = await coach.post(url, json=_training_plan(name="Coach's"))
        assert coachs.status_code == 201
        coachs = coachs.json()
        assert coachs["author"] == "coach" and coachs["can_edit"]
        listed = {p["name"]: p["can_edit"] for p in (await coach.get(url)).json()}
        assert listed == {"Mine": False, "AI plan": True, "Coach's": True}
        assert (await coach.patch(f"{url}/{own['id']}", json={"name": "Hijack"})).status_code == 403
        assert (await coach.delete(f"{url}/{own['id']}")).status_code == 403
        assert (await coach.patch(f"{url}/{ai_id}", json={"name": "Coach-tuned"})).status_code == 200

    # The athlete edits and deletes every plan of theirs, the coach's too.
    assert (await client.patch(f"{url}/{coachs['id']}", json={"name": "Mine now"})).status_code == 200
    assert (await client.delete(f"{url}/{coachs['id']}")).status_code == 204

    async with _other_client() as stranger:
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(url)).status_code == 403
        mine = (await stranger.get("/athletes/me")).json()["id"]
        assert (await stranger.get(f"/athletes/{mine}/training-plans/{own['id']}")).status_code == 404


async def test_export_and_account_deletion_cover_training_plans(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/training-plans"
    race = await client.post(f"/athletes/{athlete_id}/competitions", json={"name": "Race", "competition_date": _day(60)})
    plan = (await client.post(url, json=_training_plan(name="Kept plan", competition_id=race.json()["id"]))).json()
    await client.post(f"/athletes/{athlete_id}/planned-sessions", json=_session(2, "In it", plan["id"]))
    async with _coach_of(db_session, athlete_id) as coach:
        (await coach.post(url, json=_training_plan(name="By the coach"))).json()
        assert (await coach.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    after = {p["name"]: p["created_by_name"] for p in (await client.get(url)).json()}
    assert after == {"Kept plan": "Rider", "By the coach": None}

    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    assert "Kept plan" in archive.read("training_plans.csv").decode()
    user_id = uuid.UUID((await client.get("/auth/me")).json()["id"])
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, user_id, uuid.UUID(athlete_id)) == []
        assert (await session.scalars(select(TrainingPlan))).all() == []
        assert (await session.scalars(select(PlannedSession))).all() == []

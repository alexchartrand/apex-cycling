"""Planned workouts pushed to the athlete's Intervals.icu calendar."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

import app.ingestion.jobs as jobs
from app.connections.intervals_router import get_intervals_client, get_plan_pusher, get_session_factory
from app.db.base import utcnow
from app.ingestion.intervals.client import IntervalsAuthError, IntervalsClientError, IntervalsRateLimited
from app.ingestion.intervals.factory import build_plan_push_service
from app.ingestion.intervals.push_service import MAX_ATTEMPTS
from app.main import app as real_app
from app.planning.models import IntervalsPlanEvent
from tests.test_account import PASSWORD, _rows_referencing
from tests.test_activity_fusion import _coach_of
from tests.test_intervals_sync import FakeIntervals, _connect, _rider

WORKOUT = [
    {"kind": "warmup", "duration_s": 600, "power": {"unit": "ftp_pct", "low": 60}},
    {"type": "repeat", "count": 3, "steps": [{"label": "Flying", "event_key": "f200"}, {"kind": "recovery", "laps": 3}]},
]


class FakeCalendar(FakeIntervals):
    """Intervals.icu with a calendar: events by id, upserted on their uid."""

    def __init__(self) -> None:
        super().__init__()
        self.events: dict[str, dict] = {}
        self.calls: list[tuple[str, str | None]] = []
        self.failures: list[Exception] = []

    def _maybe_fail(self) -> None:
        if self.failures:
            raise self.failures.pop(0)

    async def save_event(self, api_key, event_id, event):
        self.calls.append(("save", event_id))
        self._maybe_fail()
        if event_id not in self.events:
            event_id = next((i for i, e in self.events.items() if e["uid"] == event["uid"]), None)
            event_id = event_id or str(1000 + len(self.calls))
        self.events[event_id] = dict(event)
        return event_id

    async def delete_event(self, api_key, event_id):
        self.calls.append(("delete", event_id))
        self._maybe_fail()
        self.events.pop(event_id, None)


@pytest.fixture
def calendar(db_session):
    fake = FakeCalendar()
    real_app.dependency_overrides[get_intervals_client] = lambda: fake
    real_app.dependency_overrides[get_session_factory] = lambda: db_session
    # These tests step through the worker's rounds; the push right after a
    # change has its own test below.
    real_app.dependency_overrides[get_plan_pusher] = lambda: _no_push
    return fake


async def _no_push(athlete_id) -> None:
    return None


async def _push(db_session, fake):
    async with db_session() as db:
        return await build_plan_push_service(db, client=fake).run()


def _plan(days: int = 3, **over) -> dict:
    return {
        "planned_date": (date.today() + timedelta(days=days)).isoformat(),
        "title": "Openers",
        "workout": WORKOUT,
        **over,
    }


async def _setup(client) -> tuple[str, str]:
    athlete_id = await _rider(client)
    assert (await _connect(client, athlete_id)).status_code == 200
    return athlete_id, f"/athletes/{athlete_id}/planned-sessions"


async def _switch(client, athlete_id, enabled: bool):
    return await client.put(f"/athletes/{athlete_id}/intervals/push", json={"enabled": enabled})


async def _states(client, url) -> dict[str, str | None]:
    return {p["title"]: p["intervals"] for p in (await client.get(url)).json()}


async def test_turning_it_on_pushes_the_upcoming_workouts(client, calendar, db_session):
    athlete_id, url = await _setup(client)
    await client.post(url, json=_plan(title="Upcoming"))
    await client.post(url, json=_plan(title="Past", days=-2))
    await client.post(url, json=_plan(title="No workout", workout=None))
    await client.post(url, json=_plan(title="Skipped"))
    skipped = next(p for p in (await client.get(url)).json() if p["title"] == "Skipped")
    await client.patch(f"{url}/{skipped['id']}", json={"status": "skipped"})
    # Nothing leaves until the athlete asks.
    assert (await _push(db_session, calendar)).sent == 0
    assert set((await _states(client, url)).values()) == {None}

    status = (await _switch(client, athlete_id, True)).json()
    assert status["push_plans"] is True
    assert (await _states(client, url))["Upcoming"] == "pending"
    result = await _push(db_session, calendar)

    assert (result.sent, result.failed) == (1, 0)
    [event] = calendar.events.values()
    assert event["name"] == "Upcoming" and event["category"] == "WORKOUT" and event["type"] == "Ride"
    assert event["description"].startswith("- 10m 60% intensity=warmup\n\n3x\n- Flying")
    assert await _states(client, url) == {"Upcoming": "sent", "Past": None, "No workout": None, "Skipped": None}
    # A plan made from now on goes at once, even one in the past.
    await client.post(url, json=_plan(title="Added later", days=-1))
    assert (await _push(db_session, calendar)).sent == 1
    assert len(calendar.events) == 2


async def test_edits_follow_the_plan_and_only_change_what_changed(client, calendar, db_session):
    athlete_id, url = await _setup(client)
    await _switch(client, athlete_id, True)
    plan = (await client.post(url, json=_plan())).json()
    await _push(db_session, calendar)
    [event_id] = calendar.events

    # Rescheduled and renamed: the same event is updated.
    moved = (date.today() + timedelta(days=5)).isoformat()
    await client.patch(f"{url}/{plan['id']}", json={"planned_date": moved, "title": "Moved"})
    await _push(db_session, calendar)
    assert list(calendar.events) == [event_id]
    assert calendar.events[event_id]["start_date_local"] == f"{moved}T00:00:00"
    assert calendar.events[event_id]["name"] == "Moved"

    # A change that doesn't alter the event sends nothing.
    calendar.calls.clear()
    await client.patch(f"{url}/{plan['id']}", json={"status": "done"})
    await _push(db_session, calendar)
    assert calendar.calls == []

    # Skipping removes it, planning it again brings it back.
    await client.patch(f"{url}/{plan['id']}", json={"status": "skipped"})
    assert (await _push(db_session, calendar)).removed == 1
    assert calendar.events == {}
    assert (await _states(client, url))["Moved"] is None
    await client.patch(f"{url}/{plan['id']}", json={"status": "planned"})
    await _push(db_session, calendar)
    assert len(calendar.events) == 1

    # Dropping the workout or deleting the plan removes it too.
    await client.patch(f"{url}/{plan['id']}", json={"workout": None})
    await _push(db_session, calendar)
    assert calendar.events == {}
    other = (await client.post(url, json=_plan(title="Other"))).json()
    await _push(db_session, calendar)
    await client.delete(f"{url}/{other['id']}")
    assert (await _push(db_session, calendar)).removed == 1
    assert calendar.events == {}
    async with db_session() as session:
        assert (await session.scalars(select(IntervalsPlanEvent))).all() == []


async def test_an_event_deleted_on_intervals_comes_back_on_the_next_change(client, calendar, db_session):
    athlete_id, url = await _setup(client)
    await _switch(client, athlete_id, True)
    plan = (await client.post(url, json=_plan())).json()
    await _push(db_session, calendar)
    calendar.events.clear()

    await client.patch(f"{url}/{plan['id']}", json={"title": "Again"})
    await _push(db_session, calendar)

    assert [e["name"] for e in calendar.events.values()] == ["Again"]


async def test_failures_are_retried_later_then_given_up(client, calendar, db_session):
    athlete_id, url = await _setup(client)
    await _switch(client, athlete_id, True)
    await client.post(url, json=_plan())
    calendar.failures = [IntervalsClientError("Intervals.icu answered HTTP 500", 500)]

    assert (await _push(db_session, calendar)).failed == 1
    assert (await _states(client, url))["Openers"] == "failed"
    status = (await client.get(f"/athletes/{athlete_id}/intervals")).json()
    assert status["push_failures"] == 1
    # Not due again yet.
    calendar.calls.clear()
    await _push(db_session, calendar)
    assert calendar.calls == []

    async with db_session() as session:
        row = await session.scalar(select(IntervalsPlanEvent))
        row.due_at = utcnow()
        await session.commit()
    assert (await _push(db_session, calendar)).sent == 1
    assert (await _states(client, url))["Openers"] == "sent"
    assert (await client.get(f"/athletes/{athlete_id}/intervals")).json()["push_failures"] == 0

    # After too many attempts it waits for the plan to change.
    plan = (await client.get(url)).json()[0]
    await client.patch(f"{url}/{plan['id']}", json={"title": "Broken"})
    async with db_session() as session:
        row = await session.scalar(select(IntervalsPlanEvent))
        row.attempts = MAX_ATTEMPTS - 1
        await session.commit()
    calendar.failures = [IntervalsClientError("boom", 500)]
    await _push(db_session, calendar)
    async with db_session() as session:
        row = await session.scalar(select(IntervalsPlanEvent))
        assert row.due_at is None and row.last_error == "boom"
    await client.patch(f"{url}/{plan['id']}", json={"title": "Fixed"})
    assert (await _push(db_session, calendar)).sent == 1


async def test_a_rate_limit_ends_the_round_and_a_refused_key_skips_the_athlete(client, calendar, db_session):
    athlete_id, url = await _setup(client)
    await _switch(client, athlete_id, True)
    for title in ("A", "B", "C"):
        await client.post(url, json=_plan(title=title))

    calendar.failures = [IntervalsRateLimited(30)]
    result = await _push(db_session, calendar)
    assert result.rate_limited and len(calendar.calls) == 1
    async with db_session() as session:
        postponed = [r for r in (await session.scalars(select(IntervalsPlanEvent))).all() if r.attempts == 0]
        assert len(postponed) == 3  # a rate limit isn't counted as an attempt

    calendar.calls.clear()
    calendar.failures = [IntervalsAuthError("refused", 401)]
    result = await _push(db_session, calendar)
    assert (result.sent, result.failed) == (0, 1) and len(calendar.calls) == 1


async def test_turning_it_off_removes_upcoming_events_and_forgets_past_ones(client, calendar, db_session):
    athlete_id, url = await _setup(client)
    await _switch(client, athlete_id, True)
    await client.post(url, json=_plan(title="Past", days=-1))
    await client.post(url, json=_plan(title="Upcoming"))
    await _push(db_session, calendar)
    assert len(calendar.events) == 2

    assert (await _switch(client, athlete_id, False)).json()["push_plans"] is False
    assert (await _push(db_session, calendar)).removed == 1
    assert [e["name"] for e in calendar.events.values()] == ["Past"]
    assert await _states(client, url) == {"Past": None, "Upcoming": None}
    # New plans stay here.
    await client.post(url, json=_plan(title="Later"))
    assert (await _push(db_session, calendar)).sent == 0


async def test_disconnecting_stops_the_push_and_keeps_the_events(client, calendar, db_session):
    athlete_id, url = await _setup(client)
    await _switch(client, athlete_id, True)
    plan = (await client.post(url, json=_plan())).json()
    await _push(db_session, calendar)

    status = (await client.delete(f"/athletes/{athlete_id}/intervals")).json()
    assert status["push_plans"] is False
    await client.delete(f"{url}/{plan['id']}")
    await _push(db_session, calendar)
    assert len(calendar.events) == 1
    async with db_session() as session:
        assert (await session.scalars(select(IntervalsPlanEvent))).all() == []
    assert (await _switch(client, athlete_id, True)).status_code == 409


async def test_only_the_athlete_turns_it_on(client, calendar, db_session):
    athlete_id = await _rider(client)
    assert (await _switch(client, athlete_id, True)).status_code == 409  # not connected
    await _connect(client, athlete_id)
    async with _coach_of(db_session, athlete_id) as coach_client:
        assert (await _switch(coach_client, athlete_id, True)).status_code == 403
        # A coach's plan is pushed like any other once the athlete turned it on.
        await _switch(client, athlete_id, True)
        created = await coach_client.post(f"/athletes/{athlete_id}/planned-sessions", json=_plan(title="From coach"))
        assert created.json()["intervals"] == "pending"
    assert (await _push(db_session, calendar)).sent == 1


async def test_the_worker_pushes_and_account_deletion_covers_the_rows(client, calendar, db_session, monkeypatch):
    athlete_id, url = await _setup(client)
    await _switch(client, athlete_id, True)
    await client.post(url, json=_plan())
    monkeypatch.setattr(jobs, "AsyncSessionLocal", db_session)
    monkeypatch.setattr(jobs, "build_plan_push_service", lambda db: build_plan_push_service(db, client=calendar))

    assert (await jobs.push_intervals_plans()).sent == 1

    user_id = uuid.UUID((await client.get("/auth/me")).json()["id"])
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, user_id, uuid.UUID(athlete_id)) == []


async def test_a_change_goes_to_intervals_at_once(client, calendar, db_session):
    del real_app.dependency_overrides[get_plan_pusher]
    athlete_id, url = await _setup(client)
    await client.post(url, json=_plan(title="Before"))
    await _switch(client, athlete_id, True)
    # Switching on sent the upcoming plan without waiting for the worker.
    assert [e["name"] for e in calendar.events.values()] == ["Before"]

    plan = (await client.post(url, json=_plan(title="Created"))).json()
    assert sorted(e["name"] for e in calendar.events.values()) == ["Before", "Created"]
    assert (await _states(client, url))["Created"] == "sent"

    await client.patch(f"{url}/{plan['id']}", json={"title": "Edited"})
    assert sorted(e["name"] for e in calendar.events.values()) == ["Before", "Edited"]

    await client.delete(f"{url}/{plan['id']}")
    assert [e["name"] for e in calendar.events.values()] == ["Before"]
    assert (await _push(db_session, calendar)).sent == 0  # nothing left for the worker

    # A failure stays for the worker to retry.
    calendar.failures = [IntervalsClientError("Intervals.icu answered HTTP 500", 500)]
    await client.post(url, json=_plan(title="Flaky"))
    assert (await _states(client, url))["Flaky"] == "failed"


async def test_only_the_changed_athletes_plans_go(client, calendar, db_session):
    athlete_id, url = await _setup(client)
    await _switch(client, athlete_id, True)
    await client.post(url, json=_plan())
    async with db_session() as db:
        result = await build_plan_push_service(db, client=calendar).run(uuid.uuid4())
    assert result.sent == 0 and calendar.events == {}
    async with db_session() as db:
        result = await build_plan_push_service(db, client=calendar).run(uuid.UUID(athlete_id))
    assert result.sent == 1

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.athletes.dashboard import coach_dashboard
from app.auth.models import User
from app.connections.models import DataSourceConnection, IngestionRun, IngestionRunStatus
from app.core.config import get_settings
from tests.fit_builder import build_fit
from tests.test_clubs import _client, _signup
from tests.test_coach_links import _close
from tests.test_track_settings import _athlete_with_track

@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


# The fixture session is 2026-03-28 (147 laps).
TODAY = date(2026, 4, 1)


async def _coach_of(client, db_session):
    """`client` is the rider (with the 03-28 session); returns the coach client and user row."""
    athlete_id = await _athlete_with_track(client, db_session, "rider@example.com")
    coach_c = _client()
    await _signup(coach_c, "coach@example.com", "Coach")
    await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_email": "rider@example.com"})
    [request] = (await client.get("/coach-links/inbox")).json()
    await client.post(f"/coach-links/{request['id']}/accept")
    async with db_session() as session:
        coach = await session.scalar(select(User).where(User.email == "coach@example.com"))
    return coach_c, coach, athlete_id


async def test_dashboard_summarises_each_coached_athlete(client, db_session):
    coach_c, coach, athlete_id = await _coach_of(client, db_session)
    try:
        async with db_session() as session:
            [card] = await coach_dashboard(session, coach, today=TODAY)

        assert (card.athlete_id, card.athlete_name) == (athlete_id, "Rider")
        assert card.last_session is not None
        assert (card.last_session.event_date, card.last_session.lap_count) == (date(2026, 3, 28), 147)
        assert (card.this_week.sessions, card.this_week.laps) == (1, 147)
        assert (card.previous_week.sessions, card.previous_week.laps) == (0, 0)
        assert card.this_week.avg_rpe is None
        assert card.new_records > 0
        assert card.failing_transponders == [] and card.unread_comments == 0

        # Further out, the same session is last week's load and the records are no longer new.
        async with db_session() as session:
            [later] = await coach_dashboard(session, coach, today=date(2026, 4, 5))
            [much_later] = await coach_dashboard(session, coach, today=date(2026, 6, 1))
        assert (later.this_week.sessions, later.previous_week.sessions) == (0, 1)
        assert much_later.new_records == 0 and much_later.last_session is not None
        assert (much_later.this_week.sessions, much_later.previous_week.sessions) == (0, 0)
    finally:
        await _close(coach_c)


async def test_dashboard_reports_failing_syncs_unread_comments_and_rpe(client, db_session):
    coach_c, coach, athlete_id = await _coach_of(client, db_session)
    try:
        sessions = (await client.get(f"/athletes/{athlete_id}/sessions")).json()
        event_id = sessions[0]["external_event_id"]
        assert (await client.patch(f"/athletes/{athlete_id}/sessions/{event_id}", json={"rpe": 7})).status_code == 200
        await client.post(f"/athletes/{athlete_id}/sessions/{event_id}/comments", json={"body": "Tough one"})
        async with db_session() as session:
            connection = await session.scalar(select(DataSourceConnection))
            session.add(
                IngestionRun(
                    data_source_connection_id=connection.id,
                    requested_at=datetime.now(timezone.utc),
                    status=IngestionRunStatus.FAILED,
                    error_message="sqorz is down",
                )
            )
            await session.commit()

        [card] = (await coach_c.get("/coach-links/dashboard")).json()
        assert card["failing_transponders"] == ["LS-03407"]
        assert card["unread_comments"] == 1

        async with db_session() as session:
            coach_row = await session.scalar(select(User).where(User.email == "coach@example.com"))
            [direct] = await coach_dashboard(session, coach_row, today=TODAY)
        assert direct.this_week.avg_rpe == 7.0
    finally:
        await _close(coach_c)


async def test_dashboard_only_lists_active_links(client, db_session):
    coach_c, coach, athlete_id = await _coach_of(client, db_session)
    try:
        [link] = (await coach_c.get("/coach-links/athletes")).json()
        await client.post(f"/coach-links/{link['id']}/revoke")
        assert (await coach_c.get("/coach-links/dashboard")).json() == []
        async with _client() as stranger:
            await _signup(stranger, "stranger@example.com")
            assert (await stranger.get("/coach-links/dashboard")).json() == []
    finally:
        await _close(coach_c)


# --- v2: form, plan compliance, goal progress, next race ---------------------------------------


async def test_dashboard_v2_carries_form_plan_goal_and_next_race(client, db_session):
    coach_c, coach, athlete_id = await _coach_of(client, db_session)
    try:
        async with db_session() as session:
            [bare] = await coach_dashboard(session, coach, today=TODAY)
        assert (bare.form, bare.plan, bare.goal, bare.next_race) == (None, None, None, None)

        # A rated ride gives the load model something to chew on.
        ride = build_fit(
            datetime(2026, 3, 30, 15, 0, tzinfo=timezone.utc),
            [{"t": t, "power": 200, "heart_rate": 140, "cadence": 90, "speed": 10.0, "distance": 10.0 * t} for t in range(3600)],
        )
        uploaded = await client.post(
            f"/athletes/{athlete_id}/activities/upload", files=[("files", ("ride.fit", ride, "application/octet-stream"))]
        )
        activity_id = uploaded.json()[0]["activity"]["id"]
        await client.patch(f"/athletes/{athlete_id}/activities/{activity_id}", json={"rpe": 6})

        for day, status in (("2026-03-30", "done"), ("2026-03-29", "skipped"), ("2026-03-27", "planned"), ("2026-03-20", "planned")):
            plan = await client.post(f"/athletes/{athlete_id}/planned-sessions", json={"planned_date": day, "title": f"Plan {day}"})
            if status != "planned":
                await client.patch(f"/athletes/{athlete_id}/planned-sessions/{plan.json()['id']}", json={"status": status})
        await client.post(f"/athletes/{athlete_id}/planned-sessions", json={"planned_date": "2026-04-03", "title": "Next"})
        await client.post(f"/athletes/{athlete_id}/planned-sessions", json={"planned_date": "2026-05-30", "title": "Far away"})

        board = (await client.get(f"/athletes/{athlete_id}/records")).json()
        record = board[0]
        goal = await client.post(
            f"/athletes/{athlete_id}/goals",
            json={
                "event_key": record["event_key"],
                "start_type": record["start_type"],
                "target_time_ms": record["time_ms"] - 1000,
                "target_date": "2026-05-01",
            },
        )
        assert goal.status_code == 201
        await client.post(
            f"/athletes/{athlete_id}/competitions", json={"name": "Nationals", "competition_date": "2026-04-10", "priority": "A"}
        )
        await client.post(f"/athletes/{athlete_id}/competitions", json={"name": "Old", "competition_date": "2026-03-01"})

        async with db_session() as session:
            [card] = await coach_dashboard(session, coach, today=TODAY)
        assert card.form is not None and card.form.ctl > 0 and card.form.atl > card.form.ctl
        assert (card.plan.done, card.plan.skipped, card.plan.missed) == (1, 1, 2)
        assert card.plan.compliance == 0.25 and card.plan.upcoming == 1
        assert (card.goal.event_key, card.goal.achieved, card.goal.days_left) == (record["event_key"], False, 30)
        assert card.goal.best_ms == record["time_ms"]
        assert (card.next_race.name, card.next_race.days_until, card.next_race.phase) == ("Nationals", 9, "taper")
    finally:
        await _close(coach_c)


async def test_dashboard_v2_shows_the_last_reached_goal_when_none_is_open(client, db_session):
    coach_c, coach, athlete_id = await _coach_of(client, db_session)
    try:
        record = (await client.get(f"/athletes/{athlete_id}/records")).json()[0]
        await client.post(
            f"/athletes/{athlete_id}/goals",
            json={
                "event_key": record["event_key"],
                "start_type": record["start_type"],
                "target_time_ms": record["time_ms"] + 1000,
                "target_date": "2026-05-01",
            },
        )
        async with db_session() as session:
            [card] = await coach_dashboard(session, coach, today=TODAY)
        assert card.goal.achieved is True
    finally:
        await _close(coach_c)


# --- squad ---------------------------------------------------------------------------------


async def test_squad_ranks_the_coached_athletes_by_their_best(client, db_session):
    coach_c, coach, athlete_id = await _coach_of(client, db_session)
    try:
        record = (await client.get(f"/athletes/{athlete_id}/records")).json()[0]
        query = {"event_key": record["event_key"], "start_type": record["start_type"]}

        async with _client() as second:  # a second athlete, faster by hand-entered result
            await _signup(second, "second@example.com", "Second")
            second_id = (await second.get("/athletes/me")).json()["id"]
            await second.post(
                f"/athletes/{second_id}/manual-results",
                json={**query, "time_ms": record["time_ms"] - 500, "achieved_on": "2026-03-01", "venue": "Elsewhere"},
            )
            await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_email": "second@example.com"})
            [request] = (await second.get("/coach-links/inbox")).json()
            await second.post(f"/coach-links/{request['id']}/accept")
        async with _client() as third:  # coached, but with no result
            await _signup(third, "third@example.com", "Third")
            await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_email": "third@example.com"})
            [request] = (await third.get("/coach-links/inbox")).json()
            await third.post(f"/coach-links/{request['id']}/accept")

        squad = (await coach_c.get("/coach-links/squad", params=query)).json()
        assert [(r["athlete_name"], r["rank"]) for r in squad["rows"]] == [("Second", 1), ("Rider", 2), ("Third", None)]
        assert squad["rows"][0]["gap_ms"] == 0 and squad["rows"][1]["gap_ms"] == 500
        assert squad["rows"][0]["source"] == "manual" and squad["rows"][1]["source"] == "sqorz"
        assert squad["rows"][2]["time_ms"] is None

        # On the rider's own track only the rider has a result.
        track = squad["tracks"][0]
        on_track = (await coach_c.get("/coach-links/squad", params={**query, "track_id": track["id"]})).json()
        assert [r["athlete_name"] for r in on_track["rows"] if r["rank"]] == ["Rider"]

        bad = await coach_c.get("/coach-links/squad", params={"event_key": "nope", "start_type": "standing"})
        assert bad.status_code == 422
    finally:
        await _close(coach_c)


async def test_squad_lists_nobody_for_a_user_without_athletes(client):
    async with _client() as stranger:
        await _signup(stranger, "stranger@example.com")
        squad = (await stranger.get("/coach-links/squad", params={"event_key": "500m", "start_type": "standing"})).json()
        assert squad["rows"] == [] and squad["tracks"] == []


async def test_dashboard_goal_prefers_a_reached_goal_over_a_lapsed_one(client, db_session):
    coach_c, coach, athlete_id = await _coach_of(client, db_session)
    try:
        record = (await client.get(f"/athletes/{athlete_id}/records")).json()[0]
        same = {"event_key": record["event_key"], "start_type": record["start_type"]}

        async def goal_for(target_ms: int, target_date: str):
            resp = await client.post(
                f"/athletes/{athlete_id}/goals", json={**same, "target_time_ms": target_ms, "target_date": target_date}
            )
            assert resp.status_code == 201

        # Only a lapsed, unreached goal: it is shown, with a negative number of days left.
        await goal_for(record["time_ms"] - 1000, "2026-03-01")
        async with db_session() as session:
            [card] = await coach_dashboard(session, coach, today=TODAY)
        assert (card.goal.achieved, card.goal.days_left < 0) == (False, True)

        # Add a reached goal that is dated earlier: it wins over the lapsed one.
        await goal_for(record["time_ms"] + 1000, "2026-02-01")
        async with db_session() as session:
            [card] = await coach_dashboard(session, coach, today=TODAY)
        assert card.goal.achieved is True
    finally:
        await _close(coach_c)

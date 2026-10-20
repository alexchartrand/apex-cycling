from datetime import date, datetime, timezone

from sqlalchemy import select

from app.athletes.dashboard import coach_dashboard
from app.auth.models import User
from app.connections.models import DataSourceConnection, IngestionRun, IngestionRunStatus
from tests.test_clubs import _client, _signup
from tests.test_coach_links import _close
from tests.test_track_settings import _athlete_with_track

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

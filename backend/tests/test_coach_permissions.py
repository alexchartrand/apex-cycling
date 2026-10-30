"""A coach reads their athlete's data, comments on sessions and plans
sessions; everything else is the athlete's (or their club admin's)."""

import uuid
from datetime import date

import pytest

from app.core.config import get_settings
from tests.test_clubs import _client, _signup
from tests.test_coach_dashboard import _coach_of
from tests.test_coach_links import _close


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


async def test_a_coach_reads_comments_and_plans_but_writes_nothing_else(client, db_session):
    coach_c, _, athlete_id = await _coach_of(client, db_session)
    base = f"/athletes/{athlete_id}"
    try:
        [session] = (await client.get(f"{base}/sessions")).json()
        event = session["external_event_id"]
        detail = (await coach_c.get(f"{base}/sessions/{event}")).json()
        lap_id = detail["tracks"][0]["laps"][0]["lap_id"]
        bike = (await client.post(f"{base}/bikes", json={"name": "Track bike"})).json()

        refused = [
            ("patch", base, {"height_cm": 170}),
            ("post", f"{base}/metrics", {"weight_kg": 70}),
            ("post", f"{base}/goals", {}),
            ("post", f"{base}/seasons", {"name": "2027", "start_date": "2027-01-01"}),
            ("post", f"{base}/competitions", {"name": "Nationals", "competition_date": "2026-07-01"}),
            ("post", f"{base}/aero-tests", {"external_event_id": event, "label": "A"}),
            ("patch", f"{base}/sessions/{event}", {"rpe": 5}),
            ("patch", f"{base}/laps/{lap_id}", {"excluded": True}),
            ("put", f"{base}/sessions/{event}/efforts/{lap_id}/label", {"label": "x"}),
            (
                "post",
                f"{base}/manual-results",
                {"event_key": "flying_200m", "start_type": "flying", "time_ms": 11000, "achieved_on": "2026-03-01", "venue": "X"},
            ),
            ("post", f"{base}/bikes", {"name": "Coach bike"}),
            ("delete", f"{base}/bikes/{bike['id']}", None),
            ("put", f"{base}/sessions/{event}/gear", {"gear_setup_id": None}),
            ("post", f"{base}/transponder-assignments", {"transponder_code": "LS-1", "start_date": "2026-01-01"}),
        ]
        for method, url, body in refused:
            kwargs = {} if body is None else {"json": body}
            resp = await getattr(coach_c, method)(url, **kwargs)
            assert resp.status_code == 403, (method, url, resp.status_code)

        # The two things a coach does.
        resp = await coach_c.post(f"{base}/sessions/{event}/comments", json={"body": "Nice pacing"})
        assert resp.status_code == 201
        plan = {"planned_date": date(2026, 4, 3).isoformat(), "title": "Flying 200s"}
        assert (await coach_c.post(f"{base}/planned-sessions", json=plan)).status_code == 201

        # And the athlete still edits their own data.
        assert (await client.patch(f"{base}/sessions/{event}", json={"rpe": 5})).status_code == 200
    finally:
        await _close(coach_c)


async def test_a_club_admin_still_edits_a_managed_athlete(client):
    await _signup(client, "boss@example.com", "Boss")
    club = (await client.post("/clubs", json={"name": "Velo", "timezone": "UTC"})).json()
    managed = (await client.post(f"/clubs/{club['id']}/athletes", json={"display_name": "Junior"})).json()
    assert (await client.patch(f"/athletes/{managed['id']}", json={"height_cm": 160})).status_code == 200
    assert (await client.post(f"/athletes/{managed['id']}/bikes", json={"name": "Loaner"})).status_code == 201


async def test_the_summary_of_one_coached_athlete(client, db_session):
    coach_c, _, athlete_id = await _coach_of(client, db_session)
    try:
        resp = await coach_c.get(f"/coach-links/athletes/{athlete_id}/summary")
        assert resp.status_code == 200
        card = resp.json()
        assert card["athlete_id"] == str(athlete_id) and card["athlete_name"] == "Rider"
        assert card["last_session"]["lap_count"] == 147

        # Not someone I coach: the same 404 as an unknown id.
        assert (await coach_c.get(f"/coach-links/athletes/{uuid.uuid4()}/summary")).status_code == 404
        stranger = _client()
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(f"/coach-links/athletes/{athlete_id}/summary")).status_code == 404

        [link] = (await coach_c.get("/coach-links/athletes")).json()
        assert (await coach_c.post(f"/coach-links/{link['id']}/revoke")).status_code == 204
        assert (await coach_c.get(f"/coach-links/athletes/{athlete_id}/summary")).status_code == 404
        await _close(stranger)
    finally:
        await _close(coach_c)

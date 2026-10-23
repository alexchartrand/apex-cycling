"""Seasons, the race calendar, the race flag and the calendar feed."""

import io
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone

from tests.test_account import PASSWORD, _other_client, _rows_referencing, _signup
from tests.test_track_settings import _athlete_with_track
from app.seasons import planning
from app.seasons.ics import CalendarEntry, build_calendar
from app.seasons.service import _Entry, season_bests
from app.training.efforts import StartType


def _in_days(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


async def _rider(client, email="rider@example.com") -> str:
    await _signup(client, email)
    return (await client.get("/athletes/me")).json()["id"]


# --- taper countdown -----------------------------------------------------------------------


def test_countdown_phases_follow_the_priority():
    race = date(2026, 7, 20)
    assert planning.countdown(race, "A", date(2026, 7, 1)).phase == "build"
    a = planning.countdown(race, "A", date(2026, 7, 10))
    assert (a.phase, a.days_until, a.taper_starts_on, a.days_to_taper) == ("taper", 10, date(2026, 7, 10), None)
    assert planning.countdown(race, "A", date(2026, 7, 7)).days_to_taper == 3  # still building, taper ahead
    assert planning.countdown(race, "C", date(2026, 7, 7)).days_to_taper is None
    assert planning.countdown(race, "B", date(2026, 7, 10)).phase == "build"  # B's taper is 5 days
    assert planning.countdown(race, "B", date(2026, 7, 16)).phase == "taper"
    c = planning.countdown(race, "C", date(2026, 7, 19))
    assert (c.phase, c.taper_starts_on) == ("build", None)  # a C race is trained through
    assert planning.countdown(race, "A", race).phase == "race_day"
    assert planning.countdown(race, "A", date(2026, 7, 21)).phase == "past"
    assert planning.countdown(race, "A", date(2026, 7, 21)).days_until == -1


# --- the .ics text -------------------------------------------------------------------------


def test_calendar_text_is_escaped_folded_and_crlf():
    now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    long_title = "é" * 60  # 120 octets: has to fold, and never inside a character
    text = build_calendar(
        "Rider, A; B",
        [CalendarEntry("u1@x", date(2026, 7, 4), long_title, "line one\nline, two; three", "Bromont")],
        now,
    )
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
    assert "\n" not in text.replace("\r\n", "")
    assert r"X-WR-CALNAME:Rider\, A\; B" in text
    assert "DTSTART;VALUE=DATE:20260704\r\nDTEND;VALUE=DATE:20260705" in text
    assert r"DESCRIPTION:line one\nline\, two\; three" in text
    assert "DTSTAMP:20260701T120000Z" in text
    unfolded = text.replace("\r\n ", "")
    assert f"SUMMARY:{long_title}" in unfolded
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))


# --- season bests (pure) --------------------------------------------------------------------


def _entry(time_ms: int, day: date, event_key="500m") -> _Entry:
    return _Entry(None, "Bromont", "Bromont", event_key, StartType.STANDING, time_ms, day, "manual")


def test_season_best_is_compared_with_the_best_before_the_season():
    entries = [
        _entry(36_000, date(2025, 6, 1)),
        _entry(35_500, date(2026, 4, 1)),
        _entry(35_000, date(2026, 3, 1)),
        _entry(40_000, date(2026, 5, 1), "1km"),
    ]
    by_event = {b.event_key: b for b in season_bests(entries, date(2026, 1, 1), None)}
    assert (by_event["500m"].time_ms, by_event["500m"].previous_best_ms, by_event["500m"].improved) == (35_000, 36_000, True)
    assert (by_event["1km"].previous_best_ms, by_event["1km"].improved) == (None, False)

    slower = season_bests([_entry(36_000, date(2025, 6, 1)), _entry(37_000, date(2026, 3, 1))], date(2026, 1, 1), None)
    assert (slower[0].time_ms, slower[0].improved) == (37_000, False)  # a season best that is no record

    closed = season_bests(entries, date(2025, 1, 1), date(2025, 12, 31))
    assert [b.time_ms for b in closed] == [36_000]


# --- API: seasons --------------------------------------------------------------------------


async def _result(client, athlete_id, time_ms, day, event_key="500m"):
    body = {"event_key": event_key, "start_type": "standing", "time_ms": time_ms, "achieved_on": day, "venue": "Elsewhere"}
    assert (await client.post(f"/athletes/{athlete_id}/manual-results", json=body)).status_code == 201


async def test_seasons_end_where_the_next_begins_and_carry_their_bests(client):
    athlete_id = await _rider(client)
    first = (await client.post(f"/athletes/{athlete_id}/seasons", json={"name": "2025", "start_date": "2025-01-01"})).json()
    second = (await client.post(f"/athletes/{athlete_id}/seasons", json={"name": "2026", "start_date": "2026-01-01"})).json()
    assert (await client.post(f"/athletes/{athlete_id}/seasons", json={"name": "Dup", "start_date": "2026-01-01"})).status_code == 409

    listed = (await client.get(f"/athletes/{athlete_id}/seasons")).json()
    assert [s["name"] for s in listed] == ["2026", "2025"]  # newest first
    assert (listed[1]["end_date"], listed[0]["end_date"]) == ("2025-12-31", None)
    assert [s["is_current"] for s in listed] == [True, False]

    await _result(client, athlete_id, 36_000, "2025-06-01")
    await _result(client, athlete_id, 35_000, "2026-03-01")
    summary = (await client.get(f"/athletes/{athlete_id}/seasons/{second['id']}")).json()
    [best] = summary["bests"]
    assert (best["time_ms"], best["previous_best_ms"], best["improved"], best["source"]) == (35_000, 36_000, True, "manual")
    old = (await client.get(f"/athletes/{athlete_id}/seasons/{first['id']}")).json()
    assert old["bests"][0]["time_ms"] == 36_000 and old["bests"][0]["improved"] is False

    renamed = await client.patch(f"/athletes/{athlete_id}/seasons/{first['id']}", json={"name": "Winter"})
    assert renamed.json()["name"] == "Winter"
    assert (await client.patch(f"/athletes/{athlete_id}/seasons/{first['id']}", json={"start_date": None})).status_code == 422
    assert (await client.delete(f"/athletes/{athlete_id}/seasons/{first['id']}")).status_code == 204
    assert (await client.get(f"/athletes/{athlete_id}/seasons/{first['id']}")).status_code == 404


async def test_a_season_is_the_athletes_own(client):
    athlete_id = await _rider(client)
    season = (await client.post(f"/athletes/{athlete_id}/seasons", json={"name": "2026", "start_date": "2026-01-01"})).json()
    async with _other_client() as other:
        other_athlete = await _rider(other, "other@example.com")
        assert (await other.get(f"/athletes/{other_athlete}/seasons/{season['id']}")).status_code == 404
        assert (await other.get(f"/athletes/{athlete_id}/seasons")).status_code == 403


# --- API: competitions ---------------------------------------------------------------------


async def test_competitions_count_down_with_the_taper_and_tie_to_a_goal(client):
    athlete_id = await _rider(client)
    goal = (
        await client.post(
            f"/athletes/{athlete_id}/goals",
            json={"event_key": "500m", "start_type": "standing", "target_time_ms": 34_000, "target_date": _in_days(30)},
        )
    ).json()
    soon = await client.post(
        f"/athletes/{athlete_id}/competitions",
        json={"name": "Nationals", "competition_date": _in_days(6), "priority": "A", "goal_id": goal["id"], "location": " Bromont "},
    )
    assert soon.status_code == 201
    assert (soon.json()["phase"], soon.json()["days_until"], soon.json()["location"]) == ("taper", 6, "Bromont")
    assert soon.json()["goal"]["target_time_ms"] == 34_000
    await client.post(f"/athletes/{athlete_id}/competitions", json={"name": "Club race", "competition_date": _in_days(40)})
    await client.post(f"/athletes/{athlete_id}/competitions", json={"name": "Last year", "competition_date": _in_days(-20), "priority": "C"})

    listed = (await client.get(f"/athletes/{athlete_id}/competitions")).json()
    assert [c["name"] for c in listed] == ["Nationals", "Club race", "Last year"]
    assert [c["phase"] for c in listed] == ["taper", "build", "past"]
    assert listed[1]["priority"] == "B" and listed[2]["taper_starts_on"] is None
    assert [c["days_to_taper"] for c in listed] == [None, 35, None]  # in the taper / 5 days before day 40 / past

    patched = await client.patch(f"/athletes/{athlete_id}/competitions/{listed[0]['id']}", json={"priority": "C", "goal_id": None})
    assert (patched.json()["phase"], patched.json()["goal"]) == ("build", None)
    assert (await client.patch(f"/athletes/{athlete_id}/competitions/{listed[0]['id']}", json={"name": None})).status_code == 422

    async with _other_client() as other:
        other_athlete = await _rider(other, "other@example.com")
        foreign = await other.post(
            f"/athletes/{other_athlete}/competitions", json={"name": "Mine", "competition_date": _in_days(3), "goal_id": goal["id"]}
        )
        assert foreign.status_code == 404  # not their goal

    assert (await client.delete(f"/athletes/{athlete_id}/competitions/{listed[0]['id']}")).status_code == 204
    assert (await client.delete(f"/athletes/{athlete_id}/competitions/{listed[0]['id']}")).status_code == 404


# --- the race flag -------------------------------------------------------------------------


async def test_a_session_can_be_marked_as_a_race_and_shows_on_the_competition(client, db_session):
    athlete_id = str(await _athlete_with_track(client, db_session, "racer@example.com"))
    [session] = (await client.get(f"/athletes/{athlete_id}/sessions")).json()
    assert session["is_race"] is False
    event_id = session["external_event_id"]

    patched = await client.patch(f"/athletes/{athlete_id}/sessions/{event_id}", json={"is_race": True})
    assert patched.json()["is_race"] is True
    assert (await client.get(f"/athletes/{athlete_id}/sessions/{event_id}")).json()["is_race"] is True
    assert (await client.get(f"/athletes/{athlete_id}/sessions")).json()[0]["is_race"] is True
    assert (await client.patch(f"/athletes/{athlete_id}/sessions/{event_id}", json={"is_race": None})).status_code == 422

    await client.post(
        f"/athletes/{athlete_id}/competitions",
        json={"name": "Spring meet", "competition_date": session["event_date"]},
    )
    [competition] = (await client.get(f"/athletes/{athlete_id}/competitions")).json()
    assert competition["race_session_id"] == event_id

    summary_id = (
        await client.post(f"/athletes/{athlete_id}/seasons", json={"name": "2026", "start_date": "2026-01-01"})
    ).json()["id"]
    summary = (await client.get(f"/athletes/{athlete_id}/seasons/{summary_id}")).json()
    assert (summary["sessions"], summary["races"]) == (1, 1)
    assert summary["bests"] and all(b["source"] == "sqorz" and b["external_event_id"] == event_id for b in summary["bests"])


# --- the calendar feed -----------------------------------------------------------------------


async def test_the_calendar_link_serves_plans_and_races_and_can_be_replaced_or_closed(client):
    athlete_id = await _rider(client)
    assert (await client.get(f"/athletes/{athlete_id}/calendar-feed")).json() == {"enabled": False, "url": None}

    await client.post(
        f"/athletes/{athlete_id}/planned-sessions",
        json={
            "planned_date": _in_days(2),
            "title": "Starts",
            "description": "Warm up well",
            "targets": [{"label": "Standing starts", "reps": 3, "event_key": "500m", "start_type": "standing", "target_time_ms": 35_500}],
        },
    )
    skipped = (
        await client.post(f"/athletes/{athlete_id}/planned-sessions", json={"planned_date": _in_days(3), "title": "Skipped one"})
    ).json()
    await client.patch(f"/athletes/{athlete_id}/planned-sessions/{skipped['id']}", json={"status": "skipped"})
    await client.post(
        f"/athletes/{athlete_id}/competitions", json={"name": "Nationals", "competition_date": _in_days(20), "priority": "A"}
    )

    made = (await client.post(f"/athletes/{athlete_id}/calendar-feed")).json()
    assert made["enabled"] and made["url"].endswith(".ics") and "/api/calendar/" in made["url"]
    token = made["url"].rsplit("/", 1)[1].removesuffix(".ics")
    # The link is shown once: asking again only says it exists.
    assert (await client.get(f"/athletes/{athlete_id}/calendar-feed")).json() == {"enabled": True, "url": None}

    async with _other_client() as phone:  # no login: the secret is the credential
        response = await phone.get(f"/calendar/{token}.ics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/calendar")
        body = response.text.replace("\r\n ", "")
        assert "SUMMARY:Starts" in body and "Skipped one" not in body
        assert "Standing starts ×3 · 500m départ arrêté · 35.500" in body or "Standing starts ×3 · 500m standing start · 35.500" in body
        assert "🏁 Nationals (A)" in body
        assert body.count("BEGIN:VEVENT") == 3  # the plan, the race and its taper start
        assert (await phone.get("/calendar/not-a-real-token.ics")).status_code == 404

        replaced = (await client.post(f"/athletes/{athlete_id}/calendar-feed")).json()
        assert (await phone.get(f"/calendar/{token}.ics")).status_code == 404
        new_token = replaced["url"].rsplit("/", 1)[1].removesuffix(".ics")
        assert (await phone.get(f"/calendar/{new_token}.ics")).status_code == 200

        assert (await client.delete(f"/athletes/{athlete_id}/calendar-feed")).status_code == 204
        assert (await phone.get(f"/calendar/{new_token}.ics")).status_code == 404


async def test_only_the_athlete_side_manages_the_calendar_link(client, db_session):
    from tests.test_activity_fusion import _coach_of

    athlete_id = await _rider(client)
    async with _coach_of(db_session, athlete_id) as coach:
        assert (await coach.get(f"/athletes/{athlete_id}/competitions")).status_code == 200  # a coach can plan races
        assert (await coach.get(f"/athletes/{athlete_id}/calendar-feed")).status_code == 403
        assert (await coach.post(f"/athletes/{athlete_id}/calendar-feed")).status_code == 403


# --- account export and deletion -----------------------------------------------------------------


async def test_export_and_deletion_cover_seasons_competitions_and_the_feed(client, db_session):
    athlete_id = await _rider(client)
    await client.post(f"/athletes/{athlete_id}/seasons", json={"name": "Export season", "start_date": "2026-01-01"})
    goal = (
        await client.post(
            f"/athletes/{athlete_id}/goals",
            json={"event_key": "500m", "start_type": "standing", "target_time_ms": 34_000, "target_date": _in_days(30)},
        )
    ).json()
    await client.post(
        f"/athletes/{athlete_id}/competitions",
        json={"name": "Export race", "competition_date": _in_days(9), "goal_id": goal["id"]},
    )
    await client.post(f"/athletes/{athlete_id}/calendar-feed")

    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    assert "Export season" in archive.read("seasons.csv").decode()
    assert "Export race" in archive.read("competitions.csv").decode()

    user_id = uuid.UUID((await client.get("/auth/me")).json()["id"])
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, user_id, uuid.UUID(athlete_id)) == []


# --- review fixes ----------------------------------------------------------------------------------


async def test_deleting_a_goal_leaves_its_races_without_a_target(client):
    athlete_id = await _rider(client)
    goal = (
        await client.post(
            f"/athletes/{athlete_id}/goals",
            json={"event_key": "500m", "start_type": "standing", "target_time_ms": 34_000, "target_date": _in_days(30)},
        )
    ).json()
    await client.post(
        f"/athletes/{athlete_id}/competitions", json={"name": "Aiming", "competition_date": _in_days(9), "goal_id": goal["id"]}
    )
    assert (await client.delete(f"/athletes/{athlete_id}/goals/{goal['id']}")).status_code == 204
    [race] = (await client.get(f"/athletes/{athlete_id}/competitions")).json()
    assert race["name"] == "Aiming" and race["goal"] is None


async def test_a_second_calendar_link_request_that_loses_the_race_takes_over_the_row(client, db_session, monkeypatch):
    from sqlalchemy import select

    from app.athletes.models import Athlete
    from app.seasons import service
    from app.seasons.models import CalendarFeed

    athlete_id = await _rider(client)
    first = (await client.post(f"/athletes/{athlete_id}/calendar-feed")).json()["url"]

    # The second request read "no row yet" before the first one committed.
    async with db_session() as session:
        athlete = await session.get(Athlete, uuid.UUID(athlete_id))
        real_scalar = session.scalar
        calls = {"n": 0}

        async def stale_first_read(statement, *args, **kwargs):
            calls["n"] += 1
            return None if calls["n"] == 1 else await real_scalar(statement, *args, **kwargs)

        monkeypatch.setattr(session, "scalar", stale_first_read)
        second = await service.enable_feed(session, athlete)

    assert second.enabled and second.url and second.url != first
    async with db_session() as session:
        assert len((await session.scalars(select(CalendarFeed))).all()) == 1

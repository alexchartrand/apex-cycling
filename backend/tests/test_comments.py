import csv
import io
import uuid
import zipfile
from datetime import date

import pytest
from sqlalchemy import select

from app.athletes.models import Athlete
from app.training.models import SessionComment, TrainingEvent
from tests.test_clubs import PASSWORD, _client, _club, _join, _signup


async def _session(db_session, athlete_id, external_id="evt-1", name="Morning ride") -> str:
    async with db_session() as session:
        session.add(
            TrainingEvent(
                athlete_id=uuid.UUID(str(athlete_id)),
                sqorz_account_id="acc-1",
                external_event_id=external_id,
                name=name,
                event_date=date(2026, 3, 28),
            )
        )
        await session.commit()
    return external_id


async def _athlete_id(client) -> str:
    return (await client.get("/athletes/me")).json()["id"]


async def _link_coach(athlete_client, coach_client, coach_user) -> None:
    await athlete_client.post("/coach-links", json={"acting_as": "athlete", "coach_email": coach_user["email"]})
    [request] = (await coach_client.get("/coach-links/inbox")).json()
    assert (await coach_client.post(f"/coach-links/{request['id']}/accept")).status_code == 200


def _url(athlete_id, event_id="evt-1") -> str:
    return f"/athletes/{athlete_id}/sessions/{event_id}/comments"


async def _post(client, athlete_id, body, event_id="evt-1") -> dict:
    resp = await client.post(_url(athlete_id, event_id), json={"body": body})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _make_pair(client, db_session):
    """`client` is the athlete; returns (coach client, coach user, athlete id)."""
    await _signup(client, "rider@example.com", "Rider")
    athlete_id = await _athlete_id(client)
    await _session(db_session, athlete_id)
    coach_c = _client()
    coach = await _signup(coach_c, "coach@example.com", "Coach")
    await _link_coach(client, coach_c, coach)
    return coach_c, coach, athlete_id


@pytest.fixture
async def pair(client, db_session):
    coach_c, coach, athlete_id = await _make_pair(client, db_session)
    yield coach_c, coach, athlete_id
    await coach_c.aclose()


async def test_athlete_and_coach_share_a_thread(client, pair):
    coach_c, coach, athlete_id = pair
    await _post(client, athlete_id, "  Legs felt heavy today  ")
    await _post(coach_c, athlete_id, "Noted. Keep the next one easy.")

    as_athlete = (await client.get(_url(athlete_id))).json()
    assert [(c["author_name"], c["by_athlete"], c["body"]) for c in as_athlete] == [
        ("Rider", True, "Legs felt heavy today"),
        ("Coach", False, "Noted. Keep the next one easy."),
    ]
    # Each viewer is told what they can do: edit only their own, the athlete may delete any.
    assert [(c["can_edit"], c["can_delete"]) for c in as_athlete] == [(True, True), (False, True)]
    as_coach = (await coach_c.get(_url(athlete_id))).json()
    assert [(c["can_edit"], c["can_delete"]) for c in as_coach] == [(False, False), (True, True)]


async def test_only_people_with_access_can_read_or_write(client, pair):
    coach_c, coach, athlete_id = pair
    async with _client() as stranger:
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(_url(athlete_id))).status_code == 403
        assert (await stranger.post(_url(athlete_id), json={"body": "hi"})).status_code == 403

        # A coach whose link was ended is out again.
        [link] = (await coach_c.get("/coach-links/athletes")).json()
        await client.post(f"/coach-links/{link['id']}/revoke")
        assert (await coach_c.get(_url(athlete_id))).status_code == 403

        assert (await client.get(_url(athlete_id, "nope"))).status_code == 404
        assert (await client.post(_url(athlete_id, "nope"), json={"body": "hi"})).status_code == 404
        for body in ("", "   ", "x" * 4001):
            assert (await client.post(_url(athlete_id), json={"body": body})).status_code == 422


async def test_edit_and_delete_rules(client, db_session, pair):
    coach_c, coach, athlete_id = pair
    mine = await _post(client, athlete_id, "My note")
    theirs = await _post(coach_c, athlete_id, "Coach note")

    edited = await coach_c.patch(f"{_url(athlete_id)}/{theirs['id']}", json={"body": "Coach note, revised"})
    assert edited.status_code == 200
    assert (edited.json()["body"], edited.json()["edited_at"] is not None) == ("Coach note, revised", True)
    assert (await client.patch(f"{_url(athlete_id)}/{theirs['id']}", json={"body": "hijack"})).status_code == 403
    assert (await coach_c.patch(f"{_url(athlete_id)}/{mine['id']}", json={"body": "hijack"})).status_code == 403
    assert (await client.patch(f"{_url(athlete_id)}/{mine['id']}", json={"body": " "})).status_code == 422

    # The coach can't remove the athlete's words; the athlete can remove the coach's.
    assert (await coach_c.delete(f"{_url(athlete_id)}/{mine['id']}")).status_code == 403
    assert (await client.delete(f"{_url(athlete_id)}/{theirs['id']}")).status_code == 204
    assert (await client.delete(f"{_url(athlete_id)}/{theirs['id']}")).status_code == 404
    assert (await coach_c.delete(f"{_url(athlete_id)}/{uuid.uuid4()}")).status_code == 404
    assert [c["id"] for c in (await client.get(_url(athlete_id))).json()] == [mine["id"]]

    # Comments belong to their own session.
    await _session(db_session, athlete_id, "evt-2")
    assert (await client.delete(f"{_url(athlete_id, 'evt-2')}/{mine['id']}")).status_code == 404


async def test_inbox_shows_other_peoples_unread_comments(client, db_session, pair):
    coach_c, coach, athlete_id = pair
    await _session(db_session, athlete_id, "evt-2", name="Track night")
    assert (await client.get("/comments/inbox")).json() == []

    await _post(coach_c, athlete_id, "How did the standing starts go?")
    await _post(coach_c, athlete_id, "x" * 300, event_id="evt-2")
    await _post(coach_c, athlete_id, "Also: send me your gearing.", event_id="evt-2")

    inbox = (await client.get("/comments/inbox")).json()
    assert [(i["external_event_id"], i["unread_count"], i["athlete_name"]) for i in inbox] == [
        ("evt-2", 2, "Rider"),
        ("evt-1", 1, "Rider"),
    ]
    assert inbox[0]["latest_excerpt"] == "Also: send me your gearing."
    assert inbox[0]["latest_author_name"] == "Coach" and inbox[0]["event_name"] == "Track night"
    # Your own comments are never new to you.
    assert (await coach_c.get("/comments/inbox")).json() == []

    # Opening a thread clears it, until someone writes again.
    assert (await client.post(f"{_url(athlete_id, 'evt-2')}/read")).status_code == 204
    assert [i["external_event_id"] for i in (await client.get("/comments/inbox")).json()] == ["evt-1"]
    await _post(coach_c, athlete_id, "One more thing", event_id="evt-2")
    assert {i["external_event_id"]: i["unread_count"] for i in (await client.get("/comments/inbox")).json()} == {
        "evt-1": 1,
        "evt-2": 1,
    }

    # Replying counts as having read the thread; the coach now has the reply waiting.
    await _post(client, athlete_id, "Fine, thanks", event_id="evt-1")
    assert [i["external_event_id"] for i in (await client.get("/comments/inbox")).json()] == ["evt-2"]
    [waiting] = (await coach_c.get("/comments/inbox")).json()
    assert (waiting["external_event_id"], waiting["latest_author_name"]) == ("evt-1", "Rider")

    # Ending the link takes the athlete's threads out of the coach's inbox.
    [link] = (await coach_c.get("/coach-links/athletes")).json()
    await client.post(f"/coach-links/{link['id']}/revoke")
    assert (await coach_c.get("/comments/inbox")).json() == []


async def test_club_admins_reach_managed_athletes_threads(client, db_session):
    await _signup(client, "admin@example.com", "Admin")
    club = await _club(client)
    junior = (await client.post(f"/clubs/{club['id']}/athletes", json={"display_name": "Junior"})).json()
    await _session(db_session, junior["id"])
    async with _client() as coach_c:
        coach = await _signup(coach_c, "coach@example.com", "Coach")
        await _join(coach_c, client, club["id"], "coach")
        await client.post(
            "/coach-links", json={"acting_as": "athlete", "athlete_id": junior["id"], "coach_user_id": coach["id"]}
        )

        await _post(coach_c, junior["id"], "Nice progress")
        [item] = (await client.get("/comments/inbox")).json()
        assert (item["athlete_name"], item["unread_count"]) == ("Junior", 1)
        # The junior has no login, so the admin stands in for them: may delete the coach's comment.
        [comment] = (await client.get(_url(junior["id"]))).json()
        assert comment["by_athlete"] is False and comment["can_delete"] is True
        assert (await client.delete(f"{_url(junior['id'])}/{comment['id']}")).status_code == 204


async def test_comments_follow_account_deletion(client, db_session, pair):
    coach_c, coach, athlete_id = pair
    await _post(client, athlete_id, "Mine")
    await _post(coach_c, athlete_id, "Coach's")
    await client.get("/comments/inbox")
    await coach_c.post(f"{_url(athlete_id)}/read")

    # A leaving coach takes their own words with them; the rest of the thread stays.
    assert (await coach_c.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    assert [c["body"] for c in (await client.get(_url(athlete_id))).json()] == ["Mine"]

    # The athlete leaving takes the whole thread, with nothing left pointing at the session.
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert (await session.scalars(select(SessionComment))).all() == []
        assert (await session.scalars(select(TrainingEvent))).all() == []
        assert (await session.scalars(select(Athlete))).all() == []


async def test_export_includes_the_thread(client, pair):
    coach_c, coach, athlete_id = pair
    await _post(client, athlete_id, "Mine")
    await _post(coach_c, athlete_id, "Coach's")
    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    rows = list(csv.DictReader(io.StringIO(archive.read("session_comments.csv").decode())))
    assert [r["body"] for r in rows] == ["Mine", "Coach's"]

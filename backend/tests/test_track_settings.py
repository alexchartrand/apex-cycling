import json
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.athletes.models import Athlete
from app.auth.models import User
from app.connections.service import create_transponder_assignment
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.training.models import Track, TrackLoop
from app.training.records_service import recompute_personal_records

_FIXTURE = Path(__file__).parent / "fixtures" / "LS-03407.json"
# The 2026-03-28 session of the Bromont "Tour complet" track: 147 laps, loops
# include "Courbe 1/2", views include "200m".
_SESSION_DATE = "2026-03-28"
_EXTERNAL_TRACK_ID = "mll61fq6"


async def _signup(client, email):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "Correcthorse123!", "display_name": "Rider"}
    )
    assert resp.status_code == 201
    return resp.json()


async def _set_admin(db_session, user_id: str, value: bool = True):
    async with db_session() as session:
        (await session.get(User, uuid.UUID(user_id))).is_platform_admin = value
        await session.commit()


async def _athlete_with_track(client, db_session, email="tracks@example.com", admin=False):
    user = await _signup(client, email)
    if admin:
        await _set_admin(db_session, user["id"])
    async with db_session() as session:
        athlete = await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(user["id"])))
        athlete_id = athlete.id
        await create_transponder_assignment(
            session,
            athlete_id=athlete_id,
            transponder_code="LS-03407",
            start_date=date(2025, 1, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user["id"]),
            notes=None,
        )
        await session.commit()
    payload = json.loads(_FIXTURE.read_text())
    payload["eventTrainingDetails"] = [
        e for e in payload["eventTrainingDetails"] if e["trainingDetail"]["eventDate"] == _SESSION_DATE
    ]
    async with db_session() as session:
        await normalize_snapshot(session, payload)
        await recompute_personal_records(session, athlete_id)
        await session.commit()
    return athlete_id


async def _track(client, athlete_id) -> dict:
    tracks = (await client.get(f"/athletes/{athlete_id}/tracks")).json()
    return next(t for t in tracks if t["name"] == "Tour complet")


async def test_courbe_loops_start_hidden_and_other_loops_do_not(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session)
    track = await _track(client, athlete_id)
    hidden = {loop["name"] for loop in track["loops"] if loop["hidden"]}
    shown = {loop["name"] for loop in track["loops"] if not loop["hidden"]}
    assert hidden == {"Courbe 1", "Courbe 2"}
    assert {"Poursuite 1", "Poursuite 2", "Finish", "200m"} <= shown
    assert not any(view["hidden"] for view in track["views"])


async def test_a_resync_does_not_reset_hidden_loops(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session, admin=True)
    track = await _track(client, athlete_id)
    everything_shown = await client.patch(f"/tracks/{track['id']}", json={"hidden_loop_ids": []})
    assert not any(loop["hidden"] for loop in everything_shown.json()["loops"])

    payload = json.loads(_FIXTURE.read_text())
    payload["eventTrainingDetails"] = [
        e for e in payload["eventTrainingDetails"] if e["trainingDetail"]["eventDate"] == _SESSION_DATE
    ]
    async with db_session() as session:
        await normalize_snapshot(session, payload)
        await session.commit()
    assert not any(loop["hidden"] for loop in (await _track(client, athlete_id))["loops"])


async def test_only_platform_admins_can_edit_a_track(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session)
    track = await _track(client, athlete_id)
    assert track["can_edit"] is False
    assert (await client.patch(f"/tracks/{track['id']}", json={"length_m": 250})).status_code == 403

    me = (await client.get("/auth/me")).json()
    await _set_admin(db_session, me["id"])
    assert (await _track(client, athlete_id))["can_edit"] is True
    assert (await client.patch(f"/tracks/{track['id']}", json={"length_m": 250})).status_code == 200


async def test_edit_requires_a_login_and_an_existing_track(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session, admin=True)
    assert (await client.patch(f"/tracks/{uuid.uuid4()}", json={"length_m": 250})).status_code == 404
    client.cookies.clear()
    track_id = uuid.uuid4()
    assert (await client.patch(f"/tracks/{track_id}", json={"length_m": 250})).status_code == 401
    assert athlete_id  # (the athlete exists; only the session was dropped)


async def test_track_facts_are_saved_and_can_be_cleared(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session, admin=True)
    track = await _track(client, athlete_id)
    url = f"/tracks/{track['id']}"

    resp = await client.patch(url, json={"length_m": 250, "indoor": True, "elevation_m": 120.5, "default_temp_c": 27})
    assert resp.status_code == 200
    body = resp.json()
    assert (body["length_m"], body["indoor"], body["elevation_m"], body["default_temp_c"]) == (250, True, 120.5, 27)
    assert body["can_edit"] is True
    assert (await _track(client, athlete_id))["length_m"] == 250

    # Only what's sent changes; null clears.
    resp = await client.patch(url, json={"elevation_m": None})
    body = resp.json()
    assert (body["length_m"], body["indoor"], body["elevation_m"], body["default_temp_c"]) == (250, True, None, 27)


async def test_hidden_loops_and_views_are_replaced_as_a_set(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session, admin=True)
    track = await _track(client, athlete_id)
    pursuit = next(loop for loop in track["loops"] if loop["name"] == "Poursuite 1")
    view = next(v for v in track["views"] if v["name"] == "50m + 200m")
    url = f"/tracks/{track['id']}"

    body = (await client.patch(url, json={"hidden_loop_ids": [pursuit["id"]], "hidden_view_ids": [view["id"]]})).json()
    assert {loop["name"] for loop in body["loops"] if loop["hidden"]} == {"Poursuite 1"}  # Courbe is shown again
    assert {v["name"] for v in body["views"] if v["hidden"]} == {"50m + 200m"}

    # Sending only loops leaves the views alone.
    body = (await client.patch(url, json={"hidden_loop_ids": []})).json()
    assert not any(loop["hidden"] for loop in body["loops"])
    assert {v["name"] for v in body["views"] if v["hidden"]} == {"50m + 200m"}


async def test_track_settings_validation(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session, admin=True)
    track = await _track(client, athlete_id)
    url = f"/tracks/{track['id']}"
    for bad in [
        {"length_m": 0},
        {"length_m": -250},
        {"length_m": 5000},
        {"default_temp_c": 99},
        {"elevation_m": 99999},
        {"hidden_loop_ids": None},
        {"hidden_view_ids": None},
        {"hidden_loop_ids": ["not-a-uuid"]},
    ]:
        assert (await client.patch(url, json=bad)).status_code == 422, bad
    # A loop id from some other track is refused, and nothing is half-applied.
    async with db_session() as session:
        other = Track(sqorz_account_id="acc", external_track_id="other", name="Other")
        session.add(other)
        await session.flush()
        foreign_loop = TrackLoop(track_id=other.id, external_loop_id="x", name="X")
        session.add(foreign_loop)
        await session.commit()
        foreign_id = str(foreign_loop.id)
    resp = await client.patch(url, json={"length_m": 333, "hidden_loop_ids": [foreign_id]})
    assert resp.status_code == 422
    assert (await _track(client, athlete_id))["length_m"] is None


async def test_changing_the_length_recomputes_everyones_records(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session, admin=True)
    track = await _track(client, athlete_id)

    def events(board):
        return {e["event_key"] for e in board if e["place"] == "Tour complet"}

    assert events((await client.get(f"/athletes/{athlete_id}/records")).json()) == {"f200", "lap"}

    await client.patch(f"/tracks/{track['id']}", json={"length_m": 250})
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    assert {"f200", "lap", "500m", "1km", "4km"} <= events(board)

    await client.patch(f"/tracks/{track['id']}", json={"length_m": None})
    assert events((await client.get(f"/athletes/{athlete_id}/records")).json()) == {"f200", "lap"}

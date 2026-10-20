import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.athletes.models import Athlete
from app.connections.service import create_transponder_assignment
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.main import app as real_app
from app.training.distances import lap_windows
from app.training.efforts import CheckpointCrossing, LapInput, StartType, detect_efforts
from app.training.models import TrainingEvent, TrainingLap, Track
from app.training.records import session_results
from app.training.records_service import recompute_personal_records

_T0 = datetime(2026, 7, 7, 13, 0, 0, tzinfo=timezone.utc)


def _laps(totals: list[int], excluded: set[int] = frozenset()) -> list[LapInput]:
    laps, cursor = [], 0
    for index, total in enumerate(totals):
        laps.append(
            LapInput(
                lap_id=uuid.uuid4(),
                start_time=_T0 + timedelta(milliseconds=cursor),
                from_start=True,
                crossings=(CheckpointCrossing(uuid.uuid4(), "Finish", total),),
                excluded=index in excluded,
            )
        )
        cursor += total
    return laps


# --- exclusion in the pure rules ------------------------------------------


def test_excluded_lap_stays_in_the_effort_but_is_not_the_best_lap():
    [effort] = detect_efforts(_laps([25000, 17000, 24000], excluded={1}), 250)
    assert len(effort.laps) == 3  # the laps around it stay chained
    assert effort.best_lap_ms == 24000
    assert effort.lap_times_ms == (25000, 17000, 24000)  # the raw timing is still reported


def test_a_window_cannot_include_an_excluded_lap():
    [effort] = detect_efforts(_laps([30000, 25000, 24000, 26000], excluded={2}), 250)
    assert [w.first_lap_index for w in lap_windows(effort, 2)] == [0]
    assert lap_windows(effort, 3) == []


def test_excluded_laps_never_set_records():
    laps = _laps([30000, 25000, 15000, 26000, 25500], excluded={2})
    results = {
        (r.event_key, r.start_type): r.time_ms
        for r in session_results(
            track_id=uuid.uuid4(),
            track_length_m=250,
            training_event_id=uuid.uuid4(),
            event_date=date(2026, 7, 7),
            laps=laps,
            view_times_ms={"f200": {laps[2].lap_id: 9000, laps[3].lap_id: 13000}},
        )
    }
    assert results[("lap", StartType.FLYING)] == 25000  # not the excluded 15000
    assert results[("f200", StartType.FLYING)] == 13000  # not the excluded 9000
    assert results[("500m", StartType.FLYING)] == 51500  # laps 4-5; every window touching lap 3 is gone


# --- endpoints ---------------------------------------------------------------

_FIXTURE = Path(__file__).parent / "fixtures" / "LS-03407.json"
_EVENT_ID = "6a4c79ca77ee02beb78eacdb"  # 2026-07-07, laps 1-4 then 5-6 (see test_efforts)


def _payload() -> dict:
    payload = json.loads(_FIXTURE.read_text())
    payload["eventTrainingDetails"] = [
        e for e in payload["eventTrainingDetails"] if e["trainingDetail"]["eventId"] == _EVENT_ID
    ]
    return payload


async def _signup(client, email):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "Correcthorse123!", "display_name": "Rider"}
    )
    assert resp.status_code == 201
    return resp.json()


async def _athlete_with_session(client, db_session, email):
    user = await _signup(client, email)
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
    async with db_session() as session:
        await normalize_snapshot(session, _payload())
        for track in (await session.scalars(select(Track))).all():
            track.length_m = 250
        await recompute_personal_records(session, athlete_id)
        await session.commit()
    return athlete_id


async def test_session_edits_show_up_in_detail_and_list(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, "edit-session@example.com")
    detail = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}")).json()
    sqorz_name = detail["event_name"]
    assert detail["title_override"] is None and detail["tags"] == [] and detail["rpe"] is None

    resp = await client.patch(
        f"/athletes/{athlete_id}/sessions/{_EVENT_ID}",
        json={"title_override": " Openers ", "notes": "Felt flat early", "rpe": 7, "tags": ["Track", " openers ", "track", ""]},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "external_event_id": _EVENT_ID,
        "event_name": "Openers",
        "title_override": "Openers",
        "notes": "Felt flat early",
        "rpe": 7,
        "tags": ["Track", "openers"],  # trimmed, blanks and case-duplicates dropped
    }

    detail = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}")).json()
    assert (detail["event_name"], detail["notes"], detail["rpe"], detail["tags"]) == (
        "Openers",
        "Felt flat early",
        7,
        ["Track", "openers"],
    )
    [listed] = (await client.get(f"/athletes/{athlete_id}/sessions")).json()
    assert (listed["event_name"], listed["rpe"], listed["tags"]) == ("Openers", 7, ["Track", "openers"])

    # Only the fields sent change; null / blank clears.
    resp = await client.patch(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}", json={"title_override": "  ", "rpe": None})
    assert resp.json()["event_name"] == sqorz_name
    assert resp.json()["rpe"] is None
    assert resp.json()["notes"] == "Felt flat early"


async def test_session_edit_validation(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, "edit-invalid@example.com")
    url = f"/athletes/{athlete_id}/sessions/{_EVENT_ID}"
    assert (await client.patch(url, json={"rpe": 0})).status_code == 422
    assert (await client.patch(url, json={"rpe": 11})).status_code == 422
    assert (await client.patch(url, json={"tags": ["x" * 33]})).status_code == 422
    assert (await client.patch(url, json={"tags": [str(i) for i in range(21)]})).status_code == 422
    assert (await client.patch(url, json={"title_override": "x" * 256})).status_code == 422
    assert (await client.patch(f"/athletes/{athlete_id}/sessions/nope", json={"rpe": 5})).status_code == 404


async def test_edits_survive_a_resync(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, "edit-resync@example.com")
    await client.patch(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}", json={"title_override": "Mine", "rpe": 4})
    detail = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}")).json()
    lap_id = detail["tracks"][0]["laps"][1]["lap_id"]
    await client.patch(f"/athletes/{athlete_id}/laps/{lap_id}", json={"excluded": True, "label": "Warm-up"})
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}/efforts")).json()
    await client.put(
        f"/athletes/{athlete_id}/sessions/{_EVENT_ID}/efforts/{efforts[0]['lap_ids'][0]}/label", json={"label": "Opener"}
    )

    async with db_session() as session:
        await normalize_snapshot(session, _payload())
        await session.commit()

    detail = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}")).json()
    assert (detail["event_name"], detail["rpe"]) == ("Mine", 4)
    lap = detail["tracks"][0]["laps"][1]
    assert (lap["excluded"], lap["label"]) == (True, "Warm-up")
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}/efforts")).json()
    assert efforts[0]["label"] == "Opener"


async def test_excluding_a_lap_updates_records_and_best_lap(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, "edit-exclude@example.com")
    detail = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}")).json()
    laps = detail["tracks"][0]["laps"]
    assert laps[0]["whole_lap_time_ms"] == 28041  # the session's fastest finished lap
    assert all(lap["excluded"] is False and lap["label"] is None for lap in laps)

    def lap_record(board):
        return next(e for e in board if e["event_key"] == "lap" and e["place"] == "Tour complet")

    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    assert lap_record(board)["time_ms"] == 28041

    resp = await client.patch(f"/athletes/{athlete_id}/laps/{laps[0]['lap_id']}", json={"excluded": True})
    assert resp.status_code == 200
    assert resp.json() == {"lap_id": laps[0]["lap_id"], "excluded": True, "label": None}

    # The record moves to the next-fastest lap (28299), and the effort's best lap follows.
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    assert lap_record(board)["time_ms"] == 28299
    [effort, _] = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}/efforts")).json()
    assert effort["best_lap_ms"] == 28299
    assert effort["lap_times_ms"] == [28041, 28614, 28299, None]  # the effort itself is unchanged

    # Progression skips it too.
    track_id = (await client.get(f"/athletes/{athlete_id}/tracks")).json()[0]["id"]
    [point] = (
        await client.get(f"/athletes/{athlete_id}/progression", params={"metric": "lap_time", "track_id": track_id})
    ).json()
    assert point["time_ms"] == 28299

    # Including it again restores everything.
    await client.patch(f"/athletes/{athlete_id}/laps/{laps[0]['lap_id']}", json={"excluded": False})
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    assert lap_record(board)["time_ms"] == 28041


async def test_lap_edit_validation(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, "edit-lap-invalid@example.com")
    detail = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}")).json()
    lap_id = detail["tracks"][0]["laps"][0]["lap_id"]
    url = f"/athletes/{athlete_id}/laps/{lap_id}"
    assert (await client.patch(url, json={"excluded": None})).status_code == 422
    assert (await client.patch(url, json={"label": "x" * 101})).status_code == 422
    assert (await client.patch(f"/athletes/{athlete_id}/laps/{uuid.uuid4()}", json={"excluded": True})).status_code == 404
    resp = await client.patch(url, json={"label": "  Sprint  "})
    assert resp.json()["label"] == "Sprint"
    resp = await client.patch(url, json={"label": ""})
    assert resp.json()["label"] is None
    assert resp.json()["excluded"] is False  # untouched


async def test_effort_label_only_on_the_first_lap_of_an_effort(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, "edit-effort@example.com")
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}/efforts")).json()
    assert [e["label"] for e in efforts] == [None, None]
    base = f"/athletes/{athlete_id}/sessions/{_EVENT_ID}/efforts"

    first_lap = efforts[1]["lap_ids"][0]
    resp = await client.put(f"{base}/{first_lap}/label", json={"label": " Standing 500 "})
    assert resp.status_code == 200
    assert resp.json() == {"first_lap_id": first_lap, "label": "Standing 500"}
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}/efforts")).json()
    assert [e["label"] for e in efforts] == [None, "Standing 500"]

    middle_lap = efforts[0]["lap_ids"][1]  # a lap inside an effort doesn't start one
    assert (await client.put(f"{base}/{middle_lap}/label", json={"label": "x"})).status_code == 404
    assert (await client.put(f"{base}/{uuid.uuid4()}/label", json={"label": "x"})).status_code == 404

    cleared = await client.put(f"{base}/{first_lap}/label", json={"label": None})
    assert cleared.json()["label"] is None


async def test_edits_belong_to_the_athlete(client, db_session):
    athlete_id = await _athlete_with_session(client, db_session, "edit-owner@example.com")
    detail = (await client.get(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}")).json()
    lap_id = detail["tracks"][0]["laps"][0]["lap_id"]

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as stranger:
        other = await _signup(stranger, "edit-stranger@example.com")
        assert (await stranger.patch(f"/athletes/{athlete_id}/laps/{lap_id}", json={"excluded": True})).status_code == 403
        assert (await stranger.patch(f"/athletes/{athlete_id}/sessions/{_EVENT_ID}", json={"rpe": 1})).status_code == 403
        # Their own athlete id with the owner's lap id / session id: nothing to edit.
        async with db_session() as session:
            mine = (await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(other["id"])))).id
        assert (await stranger.patch(f"/athletes/{mine}/laps/{lap_id}", json={"excluded": True})).status_code == 404
        assert (await stranger.patch(f"/athletes/{mine}/sessions/{_EVENT_ID}", json={"rpe": 1})).status_code == 404

    async with db_session() as session:
        lap = await session.get(TrainingLap, uuid.UUID(lap_id))
        event = await session.scalar(select(TrainingEvent).where(TrainingEvent.external_event_id == _EVENT_ID))
        assert lap.excluded is False and event.rpe is None

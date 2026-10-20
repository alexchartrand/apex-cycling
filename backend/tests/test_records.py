import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.athletes.models import Athlete
from app.connections.service import create_transponder_assignment
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.ingestion.sqorz.normalizer_adapter import SqlAlchemyNormalizerAdapter, SqlAlchemyRecordsAdapter
from app.main import app as real_app
from app.training.efforts import CheckpointCrossing, LapInput, StartType
from app.training.models import PersonalRecord, Track
from app.training.records import Result, best_results, running_minimum, session_results
from app.training.records_service import recompute_personal_records

_T0 = datetime(2026, 7, 7, 13, 0, 0, tzinfo=timezone.utc)
_TRACK_ID = uuid.uuid4()
_EVENT_ID = uuid.uuid4()


def _laps(totals: list[int | None], start_ms: int = 0) -> list[LapInput]:
    laps, cursor = [], start_ms
    for total in totals:
        laps.append(
            LapInput(
                lap_id=uuid.uuid4(),
                start_time=_T0 + timedelta(milliseconds=cursor),
                from_start=True,
                crossings=(CheckpointCrossing(uuid.uuid4(), "Finish", total),),
            )
        )
        cursor += total or 0
    return laps


def _results(laps, length=250, view_times=None):
    return {
        (r.event_key, r.start_type): r
        for r in session_results(
            track_id=_TRACK_ID,
            track_length_m=length,
            training_event_id=_EVENT_ID,
            event_date=date(2026, 7, 7),
            laps=laps,
            view_times_ms=view_times or {},
        )
    }


# --- pure rules ------------------------------------------------------------


def test_session_results_standing_effort_hand_checked():
    # Standing first lap (30 s) then 25 / 24 / 26 s laps on a 250 m track.
    results = _results(_laps([30000, 25000, 24000, 26000]))
    times = {key: r.time_ms for key, r in results.items()}
    assert times == {
        # A single lap is only ever a flying record; the standing first lap doesn't count.
        ("lap", StartType.FLYING): 24000,
        ("500m", StartType.STANDING): 55000,
        ("500m", StartType.FLYING): 49000,  # laps 2-3
        ("750m", StartType.STANDING): 79000,
        ("750m", StartType.FLYING): 75000,  # laps 2-4
        ("1km", StartType.STANDING): 105000,
    }


def test_result_points_at_the_first_lap_of_the_performance():
    laps = _laps([30000, 25000, 24000, 26000])
    results = _results(laps)
    assert results[("500m", StartType.FLYING)].lap_id == laps[1].lap_id
    assert results[("500m", StartType.STANDING)].lap_id == laps[0].lap_id
    assert results[("500m", StartType.FLYING)].achieved_at == laps[1].start_time


def test_a_lone_lap_of_unknown_start_counts_as_flying():
    results = _results(_laps([22000]))
    assert results[("lap", StartType.FLYING)].time_ms == 22000


def test_without_track_length_only_single_lap_records_exist():
    assert set(_results(_laps([30000, 25000, 24000]), length=None)) == {("lap", StartType.FLYING)}


def test_flying_200_skips_the_first_lap_of_a_standing_start():
    laps = _laps([30000, 25000, 24000])
    f200 = {laps[0].lap_id: 9000, laps[1].lap_id: 13500, laps[2].lap_id: 13000}
    results = _results(laps, view_times={"f200": f200})
    assert results[("f200", StartType.FLYING)].time_ms == 13000
    assert results[("f200", StartType.FLYING)].lap_id == laps[2].lap_id


def test_flying_200_counts_the_first_lap_of_a_flying_effort():
    laps = _laps([25000, 25000, 24000])
    results = _results(laps, view_times={"f200": {laps[0].lap_id: 12500, laps[1].lap_id: 13000, laps[2].lap_id: None}})
    assert results[("f200", StartType.FLYING)].time_ms == 12500


def test_nonsense_zero_time_is_never_a_record():
    laps = _laps([25000, 25000])
    results = _results(laps, view_times={"f200": {laps[1].lap_id: 0}})
    assert ("f200", StartType.FLYING) not in results


def _result(time_ms: int, day: int, event_key="500m") -> Result:
    return Result(
        track_id=_TRACK_ID,
        event_key=event_key,
        start_type=StartType.STANDING,
        time_ms=time_ms,
        training_event_id=uuid.uuid4(),
        event_date=date(2026, 7, day),
        lap_id=uuid.uuid4(),
        achieved_at=_T0 + timedelta(days=day),
    )


def test_best_results_keeps_the_fastest_and_the_earliest_on_a_tie():
    early, tie_later, slower = _result(36000, 1), _result(36000, 5), _result(37000, 3)
    other_event = _result(70000, 2, event_key="1km")
    best = {r.event_key: r for r in best_results([tie_later, slower, early, other_event])}
    assert best["500m"] is early
    assert best["1km"] is other_event


def test_running_minimum_keeps_only_strict_improvements_in_order():
    assert running_minimum([40, 42, 38, 38, 39, 35], lambda t: t) == [40, 38, 35]
    assert running_minimum([], lambda t: t) == []


# --- persistence and endpoints --------------------------------------------

_FIXTURE = Path(__file__).parent / "fixtures" / "LS-03407.json"
# The two sessions the real-data assertions rely on (273 of the export's 936 laps),
# so each test doesn't pay for ingesting the whole file.
_SESSION_DATES = {"2026-03-28", "2026-04-04"}


def _fixture_payload() -> dict:
    payload = json.loads(_FIXTURE.read_text())
    payload["eventTrainingDetails"] = [
        e for e in payload["eventTrainingDetails"] if e["trainingDetail"]["eventDate"] in _SESSION_DATES
    ]
    return payload


async def _signup(client, email):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "Correcthorse123!", "display_name": "Rider"}
    )
    assert resp.status_code == 201
    return resp.json()


async def _athlete(client, db_session, email: str) -> uuid.UUID:
    """A signed-in athlete (the client's user) with no training data."""
    user = await _signup(client, email)
    async with db_session() as session:
        athlete = await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(user["id"])))
        return athlete.id


async def _athlete_with_fixture(client, db_session, email="records@example.com", track_length=250.0):
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
        await normalize_snapshot(session, _fixture_payload())
        if track_length is not None:
            for track in (await session.scalars(select(Track))).all():
                track.length_m = track_length
        await recompute_personal_records(session, athlete_id)
        await session.commit()
    return athlete_id


def _find(board, **fields):
    return [e for e in board if all(e[k] == v for k, v in fields.items())]


async def test_board_on_real_export_matches_the_raw_data(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session)

    board = (await client.get(f"/athletes/{athlete_id}/records")).json()

    # Best flying 200 in the export: 12970 ms (Finish minus the 200m checkpoint) on 2026-03-28.
    [f200] = _find(board, event_key="f200", place="Tour complet")
    assert (f200["time_ms"], f200["achieved_on"], f200["start_type"]) == (12970, "2026-03-28", "flying")
    assert f200["source"] == "sqorz"
    assert f200["external_event_id"] and f200["lap_id"]
    # The fastest 250 m lap in that session's long block.
    assert min(e["time_ms"] for e in _find(board, event_key="lap", place="Tour complet")) == 16177
    # Every record is one of the known events and a real start type.
    assert {e["event_key"] for e in board} <= {"f200", "lap", "500m", "750m", "1km", "2km", "3km", "4km"}
    assert {e["start_type"] for e in board} <= {"standing", "flying"}
    # Longer distances take longer.
    tour_flying = {
        e["event_key"]: e["time_ms"]
        for e in _find(board, place="Tour complet", start_type="flying")
        if e["track_id"] == f200["track_id"]
    }
    assert tour_flying["500m"] < tour_flying["1km"] < tour_flying["2km"] < tour_flying["4km"]


async def test_board_without_track_length_only_has_single_lap_and_flying_200(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "records-nolength@example.com", track_length=None)
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    assert {e["event_key"] for e in board} == {"f200", "lap"}


async def test_recompute_is_idempotent_and_drops_records_that_no_longer_apply(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "records-recompute@example.com")

    async def rows():
        async with db_session() as session:
            return (await session.scalars(select(PersonalRecord).where(PersonalRecord.athlete_id == athlete_id))).all()

    first = {(r.track_id, r.event_key, r.start_type): (r.id, r.time_ms) for r in await rows()}
    async with db_session() as session:
        await recompute_personal_records(session, athlete_id)
        await session.commit()
    second = {(r.track_id, r.event_key, r.start_type): (r.id, r.time_ms) for r in await rows()}
    assert second == first  # same rows, same ids

    async with db_session() as session:
        for track in (await session.scalars(select(Track))).all():
            track.length_m = None
        await recompute_personal_records(session, athlete_id)
        await session.commit()
    assert {r.event_key for r in await rows()} == {"f200", "lap"}


async def test_ingestion_adapters_refresh_records_for_the_athletes_that_were_written(client, db_session):
    user = await _signup(client, "records-adapter@example.com")
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
        touched = await SqlAlchemyNormalizerAdapter(session).normalize(_fixture_payload())
        assert touched == {athlete_id}
        await SqlAlchemyRecordsAdapter(session).recompute(touched)
        await session.commit()

    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    assert {e["event_key"] for e in board} == {"f200", "lap"}


async def test_manual_results_crud(client, db_session):
    athlete_id = await _athlete(client, db_session, "manual@example.com")
    body = {
        "event_key": "1km",
        "start_type": "standing",
        "time_ms": 71234,
        "achieved_on": "2026-08-01",
        "venue": "  Mont-Royal Velodrome ",
        "is_competition": True,
        "notes": "Provincials",
    }
    created = await client.post(f"/athletes/{athlete_id}/manual-results", json=body)
    assert created.status_code == 201
    result = created.json()
    assert result["venue"] == "Mont-Royal Velodrome"
    assert result["place"] == "Mont-Royal Velodrome"
    assert result["is_competition"] is True

    listed = (await client.get(f"/athletes/{athlete_id}/manual-results")).json()
    assert [r["id"] for r in listed] == [result["id"]]

    updated = await client.put(
        f"/athletes/{athlete_id}/manual-results/{result['id']}", json={**body, "time_ms": 70999}
    )
    assert updated.status_code == 200
    assert updated.json()["time_ms"] == 70999

    assert (await client.delete(f"/athletes/{athlete_id}/manual-results/{result['id']}")).status_code == 204
    assert (await client.get(f"/athletes/{athlete_id}/manual-results")).json() == []
    assert (await client.delete(f"/athletes/{athlete_id}/manual-results/{result['id']}")).status_code == 404


async def test_manual_result_validation(client, db_session):
    athlete_id = await _athlete(client, db_session, "manual-invalid@example.com")
    good = {"event_key": "500m", "start_type": "standing", "time_ms": 36000, "achieved_on": "2026-08-01", "venue": "X"}

    async def post(**changes):
        return await client.post(f"/athletes/{athlete_id}/manual-results", json={**good, **changes})

    assert (await post(event_key="marathon")).status_code == 422
    assert (await post(event_key="f200", start_type="standing")).status_code == 422  # a 200 is only flying
    assert (await post(start_type="unknown")).status_code == 422
    assert (await post(time_ms=0)).status_code == 422
    assert (await post(venue="   ")).status_code == 422  # neither a track nor a venue
    assert (await post(venue=None, track_id=str(uuid.uuid4()))).status_code == 422  # no such track
    assert (await post()).status_code == 201


async def test_manual_result_on_a_known_track_uses_the_track_as_its_place(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "manual-track@example.com")
    async with db_session() as session:
        track = await session.scalar(select(Track).where(Track.external_track_id == "mll61fq6"))
        track_id = str(track.id)

    resp = await client.post(
        f"/athletes/{athlete_id}/manual-results",
        json={
            "event_key": "500m",
            "start_type": "standing",
            "time_ms": 36000,
            "achieved_on": "2026-08-01",
            "track_id": track_id,
            "venue": "ignored",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["place"] == "Tour complet"
    assert resp.json()["venue"] is None


async def test_board_merges_manual_results_taking_the_better_time(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "merge@example.com")
    async with db_session() as session:
        track = await session.scalar(select(Track).where(Track.external_track_id == "mll61fq6"))
        track_id = str(track.id)
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    [computed] = _find(board, track_id=track_id, event_key="500m", start_type="standing")
    assert computed["source"] == "sqorz"

    base = {"event_key": "500m", "start_type": "standing", "achieved_on": "2026-08-01", "track_id": track_id}
    # A slower manual result doesn't replace the computed record...
    await client.post(f"/athletes/{athlete_id}/manual-results", json={**base, "time_ms": computed["time_ms"] + 1000})
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    [still] = _find(board, track_id=track_id, event_key="500m", start_type="standing")
    assert still["source"] == "sqorz"
    # ...a faster one does, and is flagged as a manual entry.
    faster = await client.post(
        f"/athletes/{athlete_id}/manual-results", json={**base, "time_ms": computed["time_ms"] - 1000, "is_competition": True}
    )
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    [now] = _find(board, track_id=track_id, event_key="500m", start_type="standing")
    assert (now["source"], now["time_ms"], now["is_competition"]) == ("manual", computed["time_ms"] - 1000, True)
    assert now["manual_result_id"] == faster.json()["id"]


async def test_manual_results_for_a_venue_are_their_own_place(client, db_session):
    athlete_id = await _athlete(client, db_session, "venue@example.com")
    base = {"event_key": "1km", "start_type": "standing", "venue": "Elsewhere"}
    await client.post(f"/athletes/{athlete_id}/manual-results", json={**base, "time_ms": 75000, "achieved_on": "2026-08-01"})
    await client.post(
        f"/athletes/{athlete_id}/manual-results", json={**base, "venue": "elsewhere ", "time_ms": 74000, "achieved_on": "2026-08-09"}
    )
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    [entry] = [e for e in board if e["place"].casefold() == "elsewhere"]  # one line, the faster time
    assert (entry["time_ms"], entry["track_id"], entry["source"]) == (74000, None, "manual")


async def test_record_history_is_the_chain_of_improvements(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "history@example.com")
    async with db_session() as session:
        track = await session.scalar(select(Track).where(Track.external_track_id == "mll61fq6"))
        track_id = str(track.id)

    params = {"event_key": "500m", "start_type": "standing", "track_id": track_id}
    history = (await client.get(f"/athletes/{athlete_id}/records/history", params=params)).json()
    assert len(history) >= 2
    dates = [h["achieved_on"] for h in history]
    times = [h["time_ms"] for h in history]
    assert dates == sorted(dates)
    assert all(later < earlier for earlier, later in zip(times, times[1:]))  # each one a new best
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    [current] = _find(board, track_id=track_id, event_key="500m", start_type="standing")
    assert history[-1]["time_ms"] == current["time_ms"]

    # A manual result that beats everything extends the chain.
    await client.post(
        f"/athletes/{athlete_id}/manual-results",
        json={"event_key": "500m", "start_type": "standing", "time_ms": 30000, "achieved_on": "2026-09-01", "track_id": track_id},
    )
    extended = (await client.get(f"/athletes/{athlete_id}/records/history", params=params)).json()
    assert [h["time_ms"] for h in extended] == times + [30000]
    assert extended[-1]["source"] == "manual"


async def test_record_history_for_a_manual_venue(client, db_session):
    athlete_id = await _athlete(client, db_session, "history-venue@example.com")
    base = {"event_key": "1km", "start_type": "standing", "venue": "Elsewhere"}
    for time_ms, day in [(75000, "2026-08-01"), (76000, "2026-08-05"), (74000, "2026-08-09")]:
        await client.post(f"/athletes/{athlete_id}/manual-results", json={**base, "time_ms": time_ms, "achieved_on": day})
    history = (
        await client.get(
            f"/athletes/{athlete_id}/records/history",
            params={"event_key": "1km", "start_type": "standing", "venue": "ELSEWHERE"},
        )
    ).json()
    assert [h["time_ms"] for h in history] == [75000, 74000]


async def test_records_are_private_to_the_athlete(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "private@example.com")
    created = await client.post(
        f"/athletes/{athlete_id}/manual-results",
        json={"event_key": "500m", "start_type": "standing", "time_ms": 36000, "achieved_on": "2026-08-01", "venue": "X"},
    )
    result_id = created.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as stranger:
        other = await _signup(stranger, "stranger-records@example.com")
        assert (await stranger.get(f"/athletes/{athlete_id}/records")).status_code == 403
        assert (await stranger.post(f"/athletes/{athlete_id}/manual-results", json={})).status_code in (403, 422)

        # Their own athlete id with someone else's result id: not found, not editable.
        async with db_session() as session:
            mine = await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(other["id"])))
        assert (await stranger.delete(f"/athletes/{mine.id}/manual-results/{result_id}")).status_code == 404
    assert len((await client.get(f"/athletes/{athlete_id}/manual-results")).json()) == 1

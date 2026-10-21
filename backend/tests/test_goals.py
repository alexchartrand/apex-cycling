"""Goals: a target time per event, with the best so far, the gap and a predicted time."""

import io
import uuid
import zipfile
from datetime import date, timedelta

import pytest

from app.analysis import physics
from app.core.config import get_settings
from app.goals import prediction, service
from tests.test_account import PASSWORD, _other_client, _rows_referencing, _signup
from tests.test_activity_fusion import _coach_of
from tests.test_aero_api import CDA, RHO, _setup


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    # The recording in the fixtures is from June.
    monkeypatch.setattr(service, "POWER_WINDOW", timedelta(days=3650))


def _in_days(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


async def _track_id(client, athlete_id: str) -> str:
    return (await client.get(f"/athletes/{athlete_id}/tracks")).json()[0]["id"]


async def _result(client, athlete_id: str, track_id: str, time_ms: int, event_key: str = "1km", **extra) -> None:
    body = {
        "event_key": event_key,
        "start_type": "standing",
        "time_ms": time_ms,
        "achieved_on": "2026-06-01",
        "track_id": track_id,
        **extra,
    }
    assert (await client.post(f"/athletes/{athlete_id}/manual-results", json=body)).status_code == 201


def _goal(**over) -> dict:
    return {"event_key": "1km", "start_type": "standing", "target_time_ms": 70_000, "target_date": _in_days(60), **over}


# --- the pure prediction -----------------------------------------------------


def test_the_power_comes_from_the_nearest_duration_by_ratio():
    curve = [(5, 900.0), (60, 520.0), (120, 430.0), (300, 350.0)]
    assert prediction.pick_power(curve, 70) == prediction.PowerPick(60, 520.0)
    assert prediction.pick_power(curve, 100) == prediction.PowerPick(120, 430.0)  # 100/60 > 120/100
    assert prediction.pick_power(curve, 4000) == prediction.PowerPick(300, 350.0)
    assert prediction.pick_power([], 70) is None


def test_the_predicted_time_rides_at_the_given_average_power():
    setup = physics.Setup(mass_kg=82, cda_m2=0.24, rho=RHO)
    seconds = prediction.predict_time_s(1000, True, 480, setup)
    ride = physics.simulate(1000, 480, setup, standing=True)
    # A 480 W race power averages ~564 W with the start surge, so an *average* of 480 W
    # means a lower race power (~409 W) and a slower ride.
    assert seconds > ride.time_s
    assert seconds == pytest.approx(76.83, abs=0.05)
    assert physics.simulate(1000, 409.4, setup, standing=True).average_power_w == pytest.approx(480, abs=1)
    # More power or less drag is faster.
    assert prediction.predict_time_s(1000, True, 520, setup) < seconds
    assert prediction.predict_time_s(1000, True, 480, physics.Setup(82, 0.22, RHO)) < seconds
    assert prediction.predict_time_s(1000, True, 0, setup) is None


def test_the_flying_start_is_faster_than_the_standing_one():
    setup = physics.Setup(mass_kg=82, cda_m2=0.24, rho=RHO)
    assert prediction.predict_time_s(500, False, 600, setup) < prediction.predict_time_s(500, True, 600, setup)


# --- the API -----------------------------------------------------------------


async def test_a_goal_tracks_the_best_and_the_gap(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    track_id = await _track_id(client, athlete_id)
    url = f"/athletes/{athlete_id}/goals"

    created = await client.post(url, json=_goal(track_id=track_id, notes="  Nationals  "))
    assert created.status_code == 201, created.text
    goal = created.json()
    assert goal["best"] is None and goal["gap_ms"] is None and goal["achieved"] is False
    assert goal["baseline_ms"] is None and goal["progress"] is None
    assert goal["notes"] == "Nationals" and goal["track_name"] == "Test Track"
    assert goal["days_left"] in (59, 60, 61)  # the club's day may be the neighbour of the UTC one

    await _result(client, athlete_id, track_id, 75_000)
    reached = (await client.get(url)).json()[0]
    assert reached["best"]["time_ms"] == 75_000 and reached["best"]["place"] == "Test Track"
    assert reached["gap_ms"] == 5_000 and reached["achieved"] is False

    # A goal set now starts from the 75 s: 72.5 s is half way to 70 s.
    second = (await client.post(url, json=_goal(track_id=track_id, target_date=_in_days(90)))).json()
    assert second["baseline_ms"] == 75_000 and second["progress"] == 0
    await _result(client, athlete_id, track_id, 72_500)
    again = {g["id"]: g for g in (await client.get(url)).json()}
    assert again[second["id"]]["progress"] == pytest.approx(0.5)
    assert again[goal["id"]]["progress"] is None  # no starting point

    await _result(client, athlete_id, track_id, 69_000)
    final = {g["id"]: g for g in (await client.get(url)).json()}
    assert final[second["id"]]["achieved"] is True and final[second["id"]]["gap_ms"] == -1_000
    assert final[second["id"]]["progress"] == 1


async def test_goals_are_listed_by_date_and_scoped_to_track_or_anywhere(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    track_id = await _track_id(client, athlete_id)
    url = f"/athletes/{athlete_id}/goals"
    await _result(client, athlete_id, track_id, 80_000)
    await _result(client, athlete_id, track_id, 71_000, event_key="1km", venue=None, is_competition=True)
    await _result(client, athlete_id, track_id, 31_000, event_key="500m")
    # A result with only a venue still counts toward an anywhere-goal.
    elsewhere = await client.post(
        f"/athletes/{athlete_id}/manual-results",
        json={"event_key": "1km", "start_type": "standing", "time_ms": 68_000, "achieved_on": "2026-06-02", "venue": "Elsewhere"},
    )
    assert elsewhere.status_code == 201

    await client.post(url, json=_goal(target_date=_in_days(90), track_id=track_id))
    await client.post(url, json=_goal(event_key="500m", target_time_ms=30_000, target_date=_in_days(30)))
    await client.post(url, json=_goal(target_date=_in_days(10)))

    goals = (await client.get(url)).json()
    assert [g["target_date"] for g in goals] == [_in_days(10), _in_days(30), _in_days(90)]
    anywhere, five_hundred, on_track = goals
    assert anywhere["best"]["time_ms"] == 68_000 and anywhere["best"]["place"] == "Elsewhere"
    assert five_hundred["best"]["time_ms"] == 31_000
    assert on_track["best"]["time_ms"] == 71_000 and on_track["track_name"] == "Test Track"


async def test_goal_validation(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/goals"
    assert (await client.post(url, json=_goal(event_key="marathon"))).status_code == 422
    assert (await client.post(url, json=_goal(event_key="f200", start_type="standing"))).status_code == 422
    assert (await client.post(url, json=_goal(target_time_ms=0))).status_code == 422
    assert (await client.post(url, json=_goal(track_id=str(uuid.uuid4())))).status_code == 404
    assert (await client.post(url, json={"event_key": "1km", "start_type": "standing", "target_time_ms": 70000})).status_code == 422


async def test_editing_and_deleting_a_goal(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    track_id = await _track_id(client, athlete_id)
    url = f"/athletes/{athlete_id}/goals"
    goal = (await client.post(url, json=_goal(track_id=track_id, notes="Old"))).json()

    edited = await client.patch(
        f"{url}/{goal['id']}", json={"target_time_ms": 68_500, "track_id": None, "notes": None, "target_date": _in_days(120)}
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["target_time_ms"] == 68_500 and body["track_id"] is None and body["notes"] is None
    assert body["target_date"] == _in_days(120) and body["event_key"] == "1km"
    assert (await client.patch(f"{url}/{goal['id']}", json={"target_time_ms": None})).status_code == 422
    assert (await client.patch(f"{url}/{goal['id']}", json={"track_id": str(uuid.uuid4())})).status_code == 404

    assert (await client.delete(f"{url}/{goal['id']}")).status_code == 204
    assert (await client.get(url)).json() == []
    assert (await client.delete(f"{url}/{goal['id']}")).status_code == 404


async def test_the_prediction_uses_power_and_cda(client, db_session):
    athlete_id = await _setup(client, db_session)  # a recording with power, the 74 kg weigh-in
    track_id = await _track_id(client, athlete_id)
    url = f"/athletes/{athlete_id}/goals"

    before = (await client.post(url, json=_goal(track_id=track_id))).json()
    assert before["prediction"] is None and before["prediction_problem"] == "no_cda"

    saved = await client.post(
        f"/athletes/{athlete_id}/aero-tests", json={"external_event_id": "evt-aero", "label": "Hoods", "crr": 0.003}
    )
    assert saved.status_code == 201

    goal = (await client.get(url)).json()[0]
    assert goal["prediction_problem"] is None
    predicted = goal["prediction"]
    assert predicted["cda_m2"] == pytest.approx(CDA, abs=0.01) and predicted["cda_label"] == "Hoods"
    assert predicted["rider_kg"] == 74 and predicted["power_duration_s"] in (30, 60, 120)
    # Same inputs through the physics directly.
    setup = physics.Setup(mass_kg=74 + 8, cda_m2=predicted["cda_m2"], rho=RHO)
    expected = prediction.predict_time_s(1000, True, predicted["power_w"], setup)
    assert predicted["time_ms"] == pytest.approx(expected * 1000, rel=0.002)
    assert 40_000 < predicted["time_ms"] < 200_000


async def test_the_prediction_rides_the_goal_bike(client, db_session):
    athlete_id = await _setup(client, db_session)
    url = f"/athletes/{athlete_id}/goals"
    await client.post(f"/athletes/{athlete_id}/aero-tests", json={"external_event_id": "evt-aero", "label": "Hoods"})
    bike = (await client.post(f"/athletes/{athlete_id}/bikes", json={"name": "Pursuit", "weight_kg": 6.5})).json()

    default = (await client.post(url, json=_goal())).json()
    assert default["bike_id"] is None and default["prediction"]["bike_kg"] == 8  # the aero test's default bike
    on_bike = (await client.patch(f"{url}/{default['id']}", json={"bike_id": bike["id"]})).json()
    assert on_bike["bike_name"] == "Pursuit" and on_bike["prediction"]["bike_kg"] == 6.5
    assert on_bike["prediction"]["time_ms"] < default["prediction"]["time_ms"]

    async with _other_client() as stranger:
        await _signup(stranger, "stranger@example.com")
        their_athlete = (await stranger.get("/athletes/me")).json()["id"]
        their_bike = (await stranger.post(f"/athletes/{their_athlete}/bikes", json={"name": "Theirs"})).json()
    assert (await client.patch(f"{url}/{default['id']}", json={"bike_id": their_bike["id"]})).status_code == 404
    assert (await client.post(url, json=_goal(bike_id=str(uuid.uuid4())))).status_code == 404

    assert (await client.delete(f"/athletes/{athlete_id}/bikes/{bike['id']}")).status_code == 204
    after = (await client.get(url)).json()[0]
    assert after["bike_id"] is None and after["prediction"]["bike_kg"] == 8


async def test_the_prediction_says_what_is_missing(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False, weight=False)
    track_id = await _track_id(client, athlete_id)
    url = f"/athletes/{athlete_id}/goals"
    lap = (await client.post(url, json=_goal(event_key="lap", start_type="flying", target_time_ms=17_000))).json()
    assert lap["prediction_problem"] == "no_track"
    on_track = (await client.post(url, json=_goal(event_key="lap", start_type="flying", target_time_ms=17_000, track_id=track_id))).json()
    assert on_track["prediction_problem"] == "no_weight"  # the track has its length

    await client.post(
        f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-06-01", "weight_kg": 74}
    )
    kilo = (await client.get(url)).json()
    assert {g["prediction_problem"] for g in kilo} == {"no_track", "no_power"}


async def test_a_lap_goal_needs_the_track_length(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False, length_m=None)
    track_id = await _track_id(client, athlete_id)
    goal = (
        await client.post(
            f"/athletes/{athlete_id}/goals",
            json=_goal(event_key="lap", start_type="flying", target_time_ms=17_000, track_id=track_id),
        )
    ).json()
    assert goal["prediction_problem"] == "no_track_length"


async def test_a_coach_can_set_goals_but_strangers_cannot(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/goals"
    async with _coach_of(db_session, athlete_id) as coach:
        assert (await coach.post(url, json=_goal())).status_code == 201
        assert len((await coach.get(url)).json()) == 1
    goal_id = (await client.get(url)).json()[0]["id"]
    async with _other_client() as stranger:
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(url)).status_code in (403, 404)
        assert (await stranger.delete(f"{url}/{goal_id}")).status_code in (403, 404)
        mine = (await stranger.get("/athletes/me")).json()["id"]
        # A goal id is only reachable through its own athlete.
        assert (await stranger.delete(f"/athletes/{mine}/goals/{goal_id}")).status_code == 404


async def test_export_and_account_deletion_cover_goals(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    await client.post(f"/athletes/{athlete_id}/goals", json=_goal(notes="Kept goal"))

    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    assert "Kept goal" in archive.read("goals.csv").decode()

    user_id = uuid.UUID((await client.get("/auth/me")).json()["id"])
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, user_id, uuid.UUID(athlete_id)) == []

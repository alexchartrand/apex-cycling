"""Planned vs ridden for power steps: the placement on its own, then through the API."""

import time
import uuid
from datetime import date, datetime, timezone

import pytest
from pydantic import TypeAdapter
from sqlalchemy import update

from app.activities.models import Activity, ActivitySource
from app.athletes.models import AthleteMetric
from app.core.config import get_settings
from app.planning.power_matching import (
    MAX_OPEN_STEP_S,
    StepStatus,
    cumulative_distance_1hz,
    place_steps,
    score_steps,
)
from app.workouts.schemas import WorkoutItem
from app.workouts.structure import expand
from tests.fit_builder import build_fit
from tests.test_account import _signup
from tests.test_activity_fusion import _coach_of, _upload
from tests.test_planning import _plan

FTP = 250.0
STEPS = TypeAdapter(list[WorkoutItem])


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


def _steps(items: list[dict]):
    return list(expand(STEPS.validate_python(items)))


def _trace(*pieces: tuple[int, float]) -> list[float]:
    """(seconds, watts) pieces one after the other, 1 Hz."""
    return [watts for seconds, watts in pieces for _ in range(seconds)]


INTERVALS = [
    {"kind": "warmup", "duration_s": 600, "power": {"unit": "ftp_pct", "low": 55}},
    {
        "type": "repeat",
        "count": 3,
        "steps": [
            {"label": "VO2", "duration_s": 180, "power": {"unit": "ftp_pct", "low": 105}},
            {"kind": "recovery", "duration_s": 120, "power": {"unit": "ftp_pct", "low": 50}},
        ],
    },
    {"kind": "cooldown", "duration_s": 300},
]
# Rolling around for 90 s before starting; the third rep fades.
INTERVALS_RIDDEN = _trace(
    (90, 100), (600, 140), (180, 265), (120, 125), (180, 255), (120, 125), (180, 230), (120, 125), (300, 110), (45, 0)
)


def test_the_workout_is_found_where_it_was_ridden():
    steps = _steps(INTERVALS)
    windows = place_steps(steps, INTERVALS_RIDDEN, None, ftp_w=FTP, track_length_m=250)
    assert windows[0] == (90, 690)
    assert windows[1] == (690, 870) and windows[5] == (1290, 1470)
    assert windows[-1] == (1590, 1890)  # the cooldown has no target, it just follows

    outcomes = score_steps(steps, INTERVALS_RIDDEN, None, None, ftp_w=FTP, track_length_m=250)
    assert [o.step_index for o in outcomes] == [0, 1, 2, 3, 4, 5, 6]  # the cooldown has nothing to measure
    assert [o.power_status for o in outcomes] == [
        StepStatus.HIT,  # 140 W against 137.5 ± 5 %
        StepStatus.HIT,  # 265 against 262.5
        StepStatus.HIT,
        StepStatus.HIT,  # 255
        StepStatus.HIT,
        StepStatus.UNDER,  # 230
        StepStatus.HIT,
    ]
    assert outcomes[1].power_target_w == (262.5, 262.5) and outcomes[1].avg_power_w == 265
    assert all(o.cadence_status is None for o in outcomes)


def test_a_range_is_taken_as_written_and_over_is_said():
    steps = _steps([{"duration_s": 300, "power": {"unit": "watts", "low": 200, "high": 220}}])
    for watts, expected in ((205, StepStatus.HIT), (195, StepStatus.UNDER), (230, StepStatus.OVER)):
        (outcome,) = score_steps(steps, _trace((300, watts)), None, None, ftp_w=None, track_length_m=250)
        assert outcome.power_status is expected


def test_an_open_step_spans_the_gap_between_its_neighbours():
    steps = _steps(
        [
            {"duration_s": 120, "power": {"unit": "watts", "low": 300}},
            {"kind": "recovery", "label": "Roll back to the start"},  # lap button
            {"duration_s": 120, "power": {"unit": "watts", "low": 300}},
        ]
    )
    power = _trace((60, 100), (120, 300), (200, 100), (120, 300), (60, 100))
    assert place_steps(steps, power, None, ftp_w=None, track_length_m=250) == [(60, 180), (180, 380), (380, 500)]

    # Opening and closing the workout, it runs from the start and to the end of the recording.
    steps = _steps([{"label": "Warm up"}, {"duration_s": 120, "power": {"unit": "watts", "low": 300}}, {"label": "Easy"}])
    assert place_steps(steps, power[:400], None, ftp_w=None, track_length_m=250) == [(0, 60), (60, 180), (180, 400)]


def test_a_later_run_is_looked_for_only_so_far_after_the_open_step():
    steps = _steps(
        [
            {"duration_s": 60, "power": {"unit": "watts", "low": 400}},
            {"label": "Ride to the climb"},
            {"duration_s": 60, "power": {"unit": "watts", "low": 400}},
        ]
    )
    power = _trace((60, 400), (MAX_OPEN_STEP_S + 600, 150), (60, 400))
    windows = place_steps(steps, power, None, ftp_w=None, track_length_m=250)
    assert windows[2][0] <= 60 + MAX_OPEN_STEP_S


def test_a_distance_step_lasts_until_the_recorded_distance_covers_it():
    steps = _steps(
        [
            {"distance_m": 2000, "power": {"unit": "watts", "low": 200}},
            {"kind": "recovery", "duration_s": 60, "power": {"unit": "watts", "low": 100}},
        ]
    )
    # Standing still 30 s, then 2 km at 8 m/s (250 s), then easy.
    power = _trace((30, 0), (250, 200), (60, 100))
    times = list(range(len(power)))
    speeds = [0.0] * 30 + [8.0] * 250 + [5.0] * 60
    distance, covered = [], 0.0
    for speed in speeds:
        distance.append(covered)
        covered += speed
    series = cumulative_distance_1hz(times, distance)
    assert place_steps(steps, power, series, ftp_w=None, track_length_m=250) == [(30, 280), (280, 340)]
    # A trainer's distance that never grows is no distance.
    flat = cumulative_distance_1hz(times, [0.0] * len(times))
    first = place_steps(steps, power, flat, ftp_w=None, track_length_m=250)[0]
    assert first[1] - first[0] == round(2000 / 14)  # the nominal pace of an effort


def test_cumulative_distance_holds_the_latest_reading_and_never_goes_back():
    assert cumulative_distance_1hz([0, 1, 2.5, 4], [0, 10, None, 5]) == [0, 10, 10, 10, 10]


def test_targets_that_cant_be_measured():
    steps = _steps(
        [
            {"duration_s": 120, "power": {"unit": "ftp_pct", "low": 90}},  # no FTP
            {"duration_s": 120, "power": {"unit": "watts", "low": 250}, "cadence": {"low": 90, "high": 100}},
        ]
    )
    power = _trace((120, 220), (120, 250))
    first, second = score_steps(steps, power, None, None, ftp_w=None, track_length_m=250)
    assert first.power_status is StepStatus.UNMEASURED and first.power_target_w is None
    assert second.power_status is StepStatus.HIT
    assert second.cadence_status is StepStatus.UNMEASURED  # the recording has no cadence

    # No power at all: nothing can be placed.
    (_, without) = score_steps(steps, None, [95.0] * 240, None, ftp_w=FTP, track_length_m=250)
    assert without.power_status is StepStatus.UNMEASURED and without.start_s is None


def test_cadence_skips_coasting_and_a_step_past_the_end_was_not_ridden():
    steps = _steps(
        [
            {"duration_s": 120, "power": {"unit": "watts", "low": 200}, "cadence": {"low": 100}},
            {"duration_s": 600, "power": {"unit": "watts", "low": 300}},
        ]
    )
    power = _trace((120, 200), (60, 300))  # stopped a minute into the second step
    cadence = [0.0] * 20 + [102.0] * 100 + [90.0] * 60
    first, second = score_steps(steps, power, cadence, None, ftp_w=None, track_length_m=250)
    assert first.avg_cadence == 102 and first.cadence_status is StepStatus.HIT
    assert second.power_status is StepStatus.NOT_RIDDEN and second.avg_power_w is None


def test_a_long_ride_under_a_big_workout_is_placed_quickly():
    items = [
        {"kind": "warmup", "duration_s": 900, "power": {"unit": "ftp_pct", "low": 55}},
        {
            "type": "repeat",
            "count": 10,
            "steps": [
                {
                    "type": "repeat",
                    "count": 10,
                    "steps": [
                        {"duration_s": 30, "power": {"unit": "ftp_pct", "low": 120}},
                        {"kind": "recovery", "duration_s": 30, "power": {"unit": "ftp_pct", "low": 50}},
                    ],
                },
                {"kind": "recovery", "duration_s": 300, "power": {"unit": "ftp_pct", "low": 50}},
            ],
        },
    ]
    steps = _steps(items)
    assert len(steps) == 211
    # 20 min of riding before the workout, an hour after it: about four hours in all.
    pieces = [(1200, 120.0), (900, 137.5)] + ([(30, 300.0), (30, 125.0)] * 10 + [(300, 125.0)]) * 10 + [(3600, 120.0)]
    power = _trace(*pieces)
    began = time.perf_counter()
    windows = place_steps(steps, power, None, ftp_w=FTP, track_length_m=250)
    assert time.perf_counter() - began < 5
    assert windows[0] == (1200, 2100)


# --- through the API ---------------------------------------------------------

RIDE_START = datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc)


def _ride() -> bytes:
    return build_fit(
        RIDE_START, [{"t": t, "power": round(watts), "cadence": 95} for t, watts in enumerate(INTERVALS_RIDDEN)]
    )


async def _athlete_with_ftp(client, db_session) -> str:
    await _signup(client, "rider@example.com")
    athlete_id = (await client.get("/athletes/me")).json()["id"]
    async with db_session() as session:
        session.add(AthleteMetric(athlete_id=uuid.UUID(athlete_id), effective_date=date(2026, 1, 1), ftp_w=FTP))
        await session.commit()
    return athlete_id


async def test_a_plan_linked_to_a_ride_scores_its_power_steps(client, db_session):
    athlete_id = await _athlete_with_ftp(client, db_session)
    url = f"/athletes/{athlete_id}/planned-sessions"
    ride = await _upload(client, athlete_id, _ride())
    plan = (await client.post(url, json=_plan(targets=[], workout=INTERVALS, planned_date="2026-06-20"))).json()

    assert (await client.get(f"{url}/{plan['id']}/comparison")).status_code == 409  # nothing linked yet
    assert (await client.put(f"{url}/{plan['id']}/activity", json={"activity_id": str(uuid.uuid4())})).status_code == 404
    linked = await client.put(f"{url}/{plan['id']}/activity", json={"activity_id": ride["id"]})
    assert linked.status_code == 200, linked.text
    assert linked.json()["status"] == "done" and linked.json()["session"] is None
    assert linked.json()["activity"]["id"] == ride["id"]

    body = (await client.get(f"{url}/{plan['id']}/comparison")).json()
    assert body["reps"] == [] and body["recording"]["id"] == ride["id"]
    assert [s["power_status"] for s in body["steps"]] == ["hit"] * 5 + ["under", "hit"]
    vo2 = body["steps"][1]
    assert vo2["label"] == "VO2" and vo2["kind"] == "work" and vo2["power"] == {"unit": "ftp_pct", "low": 105, "high": None}
    assert vo2["power_low_w"] == 262.5 and vo2["start_s"] == 690 and vo2["end_s"] == 870
    assert vo2["avg_power_w"] == pytest.approx(265) and vo2["avg_cadence"] == pytest.approx(95)
    assert body["power_measured"] == 7 and body["power_hits"] == 6

    # Unlinking the ride puts it back to planned; deleting the ride keeps it done.
    unlinked = (await client.delete(f"{url}/{plan['id']}/activity")).json()
    assert unlinked["status"] == "planned" and unlinked["activity"] is None
    await client.put(f"{url}/{plan['id']}/activity", json={"activity_id": ride["id"]})
    assert (await client.delete(f"/athletes/{athlete_id}/activities/{ride['id']}")).status_code == 204
    after = (await client.get(url)).json()[0]
    assert after["status"] == "done" and after["activity"] is None


async def test_a_coach_never_gets_a_strava_rides_numbers(client, db_session):
    athlete_id = await _athlete_with_ftp(client, db_session)
    url = f"/athletes/{athlete_id}/planned-sessions"
    ride = await _upload(client, athlete_id, _ride())
    plan = (await client.post(url, json=_plan(targets=[], workout=INTERVALS, planned_date="2026-06-20"))).json()
    await client.put(f"{url}/{plan['id']}/activity", json={"activity_id": ride["id"]})
    async with db_session() as session:
        await session.execute(
            update(Activity).where(Activity.id == uuid.UUID(ride["id"])).values(source=ActivitySource.STRAVA)
        )
        await session.commit()

    assert (await client.get(f"{url}/{plan['id']}/comparison")).json()["power_hits"] == 6  # the owner still does
    async with _coach_of(db_session, athlete_id) as coach:
        seen = (await coach.get(url)).json()[0]
        assert seen["status"] == "done" and seen["activity"] is None
        body = (await coach.get(f"{url}/{plan['id']}/comparison")).json()
        assert body["recording"] is None and body["steps"] == [] and body["power_measured"] == 0
        # Nor may a coach link a ride for the athlete.
        assert (await coach.put(f"{url}/{plan['id']}/activity", json={"activity_id": ride["id"]})).status_code == 403


async def test_the_recording_of_the_linked_session_answers_too(client, db_session):
    from tests.test_aero_api import _setup

    athlete_id = await _setup(client, db_session)  # a session with a powered recording linked to it
    async with db_session() as session:
        session.add(AthleteMetric(athlete_id=uuid.UUID(athlete_id), effective_date=date(2026, 1, 1), ftp_w=FTP))
        await session.commit()
    url = f"/athletes/{athlete_id}/planned-sessions"
    workout = [{"kind": "warmup", "duration_s": 60, "power": {"unit": "watts", "low": 80}}]
    plan = (await client.post(url, json=_plan(targets=[], workout=workout))).json()
    await client.put(f"{url}/{plan['id']}/session", json={"external_event_id": "evt-aero"})

    body = (await client.get(f"{url}/{plan['id']}/comparison")).json()
    assert body["recording"] is not None
    assert body["steps"][0]["power_status"] == "hit" and body["steps"][0]["start_s"] == 0

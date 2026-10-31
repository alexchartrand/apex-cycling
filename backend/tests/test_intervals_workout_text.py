"""Planned workouts written as Intervals.icu workout text."""

import uuid
from datetime import date

from pydantic import TypeAdapter

from app.ingestion.intervals.workout_text import (
    event_payload,
    format_distance,
    format_duration,
    step_line,
    workout_text,
)
from app.workouts.schemas import WorkoutItem, WorkoutStep

_ITEMS = TypeAdapter(list[WorkoutItem])


def _step(**fields) -> WorkoutStep:
    return WorkoutStep.model_validate(fields)


def test_durations_and_distances_use_the_builder_units():
    assert [format_duration(s) for s in (45, 300, 90, 3750, 0.4)] == ["45s", "5m", "1m30s", "1h2m30s", "1s"]
    # "m" means minutes there: metres are "mtr".
    assert [format_distance(m) for m in (500, 2000, 1500)] == ["500mtr", "2km", "1500mtr"]


def test_a_timed_step_carries_its_targets_and_intensity():
    line = step_line(_step(kind="warmup", duration_s=600, power={"unit": "ftp_pct", "low": 55, "high": 65.5}))
    assert line == "- 10m 55-65.5% intensity=warmup"
    line = step_line(_step(label="Over", duration_s=120, power={"unit": "watts", "low": 320}, cadence={"low": 95, "high": 105}))
    assert line == "- Over 2m 320w 95-105rpm intensity=interval"
    assert step_line(_step(kind="recovery", distance_m=2000)) == "- 2km intensity=recovery"


def test_track_and_open_steps_end_on_the_lap_button():
    flying = _step(
        label="Flying", event_key="f200", start_type="flying", target_time_ms=11_200,
        gear={"chainring_teeth": 50, "cog_teeth": 15}, power={"unit": "ftp_pct", "low": 150},
    )  # fmt: skip
    # The target time sets the estimate: 200 m in 11.2 s.
    assert step_line(flying, "en") == (
        "- Flying – flying 200 (flying start) – 11.200 s – 50×15 11s 150% press lap intensity=interval"
    )
    assert step_line(_step(kind="recovery", laps=3), "fr") == "- 3 tours 1m15s press lap intensity=recovery"
    assert step_line(_step(label="Get ready", rpe=3)) == "- Get ready – RPE 3 1m press lap intensity=interval"


def test_free_text_cannot_turn_into_lengths_or_targets():
    line = step_line(_step(label="Z2 spin, 3x 10s sprints at 120%", notes="hold\n90rpm", duration_s=60))
    assert line == "- Z 2 spin, 3 x 10 s sprints at 120 % – hold 90 rpm 1m intensity=interval"


def test_repeats_get_their_own_block_and_nested_ones_are_unrolled():
    items = _ITEMS.validate_python(
        [
            {"kind": "warmup", "duration_s": 600},
            {"type": "repeat", "count": 3, "steps": [{"duration_s": 30}, {"kind": "recovery", "duration_s": 30}]},
            {
                "type": "repeat",
                "count": 2,
                "steps": [
                    {"type": "repeat", "count": 4, "steps": [{"duration_s": 15}]},
                    {"kind": "recovery", "duration_s": 300},
                ],
            },
            {"kind": "cooldown", "duration_s": 600},
        ]
    )
    assert workout_text(items).split("\n\n") == [
        "- 10m intensity=warmup",
        "3x\n- 30s intensity=interval\n- 30s intensity=recovery",
        "4x\n- 15s intensity=interval",
        "- 5m intensity=recovery",
        "4x\n- 15s intensity=interval",
        "- 5m intensity=recovery\n- 10m intensity=cooldown",
    ]


def test_the_event_keeps_the_plan_text_out_of_the_steps():
    plan_id = uuid.uuid4()
    payload = event_payload(
        plan_id=plan_id,
        title="Openers",
        planned_date=date(2026, 11, 3),
        description="Easy day\n- legs fresh\nthen 3x",
        items=_ITEMS.validate_python([{"duration_s": 60}]),
        locale="en-CA",
    )
    assert payload == {
        "category": "WORKOUT",
        "type": "Ride",
        "start_date_local": "2026-11-03T00:00:00",
        "name": "Openers",
        "description": "Easy day\n• legs fresh\nthen 3x.\n\n- 1m intensity=interval",
        "uid": f"apex-cycling-plan-{plan_id}",
    }

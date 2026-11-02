"""Workout files: .fit (read back with fitdecode), .zwo, .erg/.mrc, and the
routes that serve them for a library workout and a planned one."""

import io
from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import fitdecode
import pytest
from pydantic import TypeAdapter

from app.training.efforts import StartType
from app.workouts.export import ExportContext, ExportFormat, NeedsFtp, export_workout, file_stem
from app.workouts.export.common import DEFAULT_EFFORT_POWER_W, MAX_EFFORT_FRACTION, step_duration_s, trainer_steps
from app.workouts.schemas import WorkoutItem, WorkoutStep
from tests.test_account import _other_client, _signup
from tests.test_activity_fusion import _coach_of
from tests.test_aero_api import _setup

_ITEMS = TypeAdapter(list[WorkoutItem])
CREATED = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)

STEPS = [
    {"kind": "warmup", "label": "Warm-up", "duration_s": 600, "power": {"unit": "ftp_pct", "low": 50, "high": 70}},
    {
        "type": "repeat",
        "count": 3,
        "steps": [
            {
                "type": "repeat",
                "count": 2,
                "steps": [
                    {"label": "Flying", "event_key": "f200", "start_type": "flying", "target_time_ms": 11_200,
                     "gear": {"chainring_teeth": 50, "cog_teeth": 15}},
                    {"kind": "recovery", "laps": 3, "rpe": 2},
                ],
            },  # fmt: skip
            {"kind": "recovery", "duration_s": 300, "power": {"unit": "watts", "low": 120}, "cadence": {"low": 90}},
        ],
    },
    {"label": "Spin", "distance_m": 2000, "cadence": {"low": 110, "high": 120}},
    {"label": "Get ready"},
    {"kind": "cooldown", "duration_s": 600, "power": {"unit": "ftp_pct", "low": 40, "high": 55}},
]


def _items(steps=STEPS):
    return _ITEMS.validate_python(steps)


def _export(fmt: ExportFormat, steps=STEPS, **context) -> bytes:
    context.setdefault("locale", "en")
    return export_workout(
        fmt, name="Flying 200s", description="Full\nrecovery", tags=["sprint"], items=_items(steps),
        context=ExportContext(**context), created=CREATED,
    ).content  # fmt: skip


def _fit_messages(content: bytes) -> list[tuple[str, dict]]:
    reader = fitdecode.FitReader(
        io.BytesIO(content), check_crc=fitdecode.CrcCheck.RAISE, error_handling=fitdecode.ErrorHandling.RAISE
    )
    with reader:
        return [
            (frame.name, {f.name: f.value for f in frame.fields})
            for frame in reader
            if isinstance(frame, fitdecode.FitDataMessage)
        ]


# --- durations of track steps on a trainer ------------------------------------------------


def _step(**fields) -> WorkoutStep:
    return WorkoutStep.model_validate(fields)


def test_a_track_step_lasts_the_target_else_the_best_else_a_simulation():
    flying = _step(event_key="f200", start_type="flying", target_time_ms=11_200)
    assert step_duration_s(flying, ExportContext()) == pytest.approx(11.2)
    # Three laps at that pace: 750 m at 200 m / 11.2 s.
    assert step_duration_s(flying.model_copy(update={"laps": 3}), ExportContext()) == pytest.approx(42)

    kilo = _step(event_key="1km", start_type="standing")
    best = ExportContext(best_times_ms={("1km", StartType.STANDING): 66_500})
    assert step_duration_s(kilo, best) == pytest.approx(66.5)
    # The flying best doesn't stand in for a standing one…
    assert step_duration_s(kilo, ExportContext(best_times_ms={("1km", StartType.FLYING): 60_000})) != 60
    # …and with no time at all the simulator rides it, faster with more power.
    simulated = step_duration_s(kilo, ExportContext())
    assert 55 < simulated < 90
    strong = _step(event_key="1km", power={"unit": "watts", "low": DEFAULT_EFFORT_POWER_W * 2})
    assert step_duration_s(strong, ExportContext()) < simulated

    assert step_duration_s(_step(kind="recovery", laps=4), ExportContext()) == pytest.approx(100)  # 1 km at 10 m/s
    assert step_duration_s(_step(label="Open"), ExportContext()) == 60


def test_trainer_steps_unroll_repeats_and_follow_each_other():
    steps = trainer_steps(_items(), ExportContext(ftp_w=250, locale="en"))
    assert len(steps) == 1 + 3 * (2 * 2 + 1) + 3
    assert [s.start_s for s in steps[:3]] == [0, 600, 611]
    assert steps[1].cue == "Flying – flying 200 (flying start) – 11.200 s – 50×15"
    assert steps[1].is_max_effort and steps[0].is_ramp and not steps[5].is_ramp
    assert steps[5].power == (120 / 250, 120 / 250)


# --- .fit ----------------------------------------------------------------------------------


def test_fit_keeps_the_tree_with_lap_button_track_steps():
    messages = _fit_messages(_export(ExportFormat.FIT, ftp_w=250))
    names = [name for name, _ in messages]
    assert names[:2] == ["file_id", "workout"] and set(names[2:]) == {"workout_step"}
    file_id, workout = messages[0][1], messages[1][1]
    assert file_id["type"] == "workout" and file_id["time_created"] == CREATED
    assert workout["wkt_name"] == "Flying 200s" and workout["sport"] == "cycling"
    assert workout["wkt_description"] == "Full recovery"
    steps = [fields for _, fields in messages[2:]]
    assert workout["num_valid_steps"] == len(steps) == 9
    assert [s["message_index"] for s in steps] == list(range(9))

    warmup, flying, recovery_laps, inner, recovery, outer, spin, ready, cooldown = steps
    # Watts from the FTP, as watts + 1000.
    assert warmup["duration_type"] == "time" and warmup["duration_time"] == 600
    assert (warmup["custom_target_power_low"], warmup["custom_target_power_high"]) == (1125, 1175)
    assert warmup["intensity"] == "warmup" and warmup["wkt_step_name"] == "Warm-up"
    assert "notes" not in warmup or warmup["notes"] is None  # it would only repeat the name
    # A track step ends on the lap button; the cue is in its notes.
    assert flying["duration_type"] == "open" and flying["target_type"] == "open"
    assert flying["notes"] == "Flying – flying 200 (flying start) – 11.200 s – 50×15"
    assert recovery_laps["duration_type"] == "open" and recovery_laps["intensity"] == "recovery"
    # Repeats point back at their first step, the inner one first.
    assert inner["duration_type"] == "repeat_until_steps_cmplt"
    assert (inner["duration_step"], inner["repeat_steps"]) == (1, 2)
    assert (outer["duration_step"], outer["repeat_steps"]) == (1, 3)
    # A single value is a ±5 % range; cadence is the secondary target.
    assert (recovery["custom_target_power_low"], recovery["custom_target_power_high"]) == (1114, 1126)
    assert recovery["secondary_target_type"] == "cadence"
    assert (recovery["secondary_custom_target_cadence_low"], recovery["secondary_custom_target_cadence_high"]) == (85, 95)
    # A road distance keeps its distance; cadence alone is the primary target.
    assert spin["duration_type"] == "distance" and spin["duration_distance"] == 2000
    assert spin["target_type"] == "cadence" and spin["custom_target_cadence_low"] == 110
    assert ready["duration_type"] == "open" and ready["wkt_step_name"] == "Get ready"
    assert cooldown["intensity"] == "cooldown"


def test_fit_keeps_percentages_without_an_ftp_and_cuts_long_text():
    steps = [{"label": "Tempo " + "é" * 60, "notes": "x" * 500, "duration_s": 60, "power": {"unit": "ftp_pct", "low": 90}}]
    (_, step), = [m for m in _fit_messages(_export(ExportFormat.FIT, steps)) if m[0] == "workout_step"]  # fmt: skip
    # Without an FTP the value stays a percentage (under 1000), for the device's FTP.
    assert (step["custom_target_power_low"], step["custom_target_power_high"]) == (86, 94)
    assert len(step["wkt_step_name"].encode()) <= 49 and step["wkt_step_name"].startswith("Tempo é")
    assert len(step["notes"].encode()) == 254


# --- .zwo ----------------------------------------------------------------------------------


def test_zwo_stays_in_ftp_fractions_and_rides_track_steps_free():
    root = ET.fromstring(_export(ExportFormat.ZWO, ftp_w=250))
    assert root.findtext("name") == "Flying 200s" and root.findtext("sportType") == "bike"
    assert [tag.get("name") for tag in root.find("tags")] == ["sprint"]
    blocks = list(root.find("workout"))
    assert len(blocks) == 1 + 3 * 5 + 3
    warmup, flying, recovery_laps = blocks[:3]
    assert warmup.tag == "Warmup" and (warmup.get("PowerLow"), warmup.get("PowerHigh")) == ("0.5", "0.7")
    assert flying.tag == "FreeRide" and flying.get("Duration") == "11"
    assert flying.find("textevent").get("message").startswith("Flying – flying 200")
    assert recovery_laps.tag == "FreeRide" and recovery_laps.get("Duration") == "75"
    steady = blocks[5]
    assert steady.tag == "SteadyState" and steady.get("Power") == "0.48" and steady.get("Cadence") == "90"
    cooldown = blocks[-1]
    # A cooldown runs from PowerLow down to PowerHigh.
    assert cooldown.tag == "Cooldown" and (cooldown.get("PowerLow"), cooldown.get("PowerHigh")) == ("0.55", "0.4")
    # Watts with no FTP can't become a fraction: ridden free.
    without_ftp = list(ET.fromstring(_export(ExportFormat.ZWO)).find("workout"))
    assert without_ftp[5].tag == "FreeRide"


# --- .erg / .mrc ---------------------------------------------------------------------------


def _course(content: bytes) -> tuple[list[str], list[tuple[float, float]], list[str]]:
    text = content.decode()
    assert "\r\n" in text
    lines = text.split("\r\n")
    header = lines[: lines.index("[END COURSE HEADER]")]
    data = lines[lines.index("[COURSE DATA]") + 1 : lines.index("[END COURSE DATA]")]
    cues = lines[lines.index("[COURSE TEXT]") + 1 : lines.index("[END COURSE TEXT]")] if "[COURSE TEXT]" in lines else []
    points = [(float(minutes), float(value)) for minutes, value in (line.split("\t") for line in data)]
    return header, points, cues


def test_erg_is_in_watts_with_every_step_numbered():
    header, points, cues = _course(_export(ExportFormat.ERG, ftp_w=250))
    assert "FTP = 250" in header and "MINUTES WATTS" in header and "DESCRIPTION = Full recovery" in header
    assert len(points) == 2 * 19
    assert points[:2] == [(0, 125), (10, 175)]  # the warm-up ramps up
    # A track effort without a target goes all out.
    assert points[2] == (10, 250 * MAX_EFFORT_FRACTION) and points[3][0] == pytest.approx(10.18, abs=0.01)
    # RPE 2 recovery: the sRPE intensity, 0.46 × FTP.
    assert points[4][1] == 115
    assert points[-2:] == [(points[-2][0], 138), (points[-1][0], 100)]  # the cool-down ramps down
    assert all(later[0] >= earlier[0] for earlier, later in zip(points, points[1:]))
    assert cues[1].split("\t") == ["600", "Flying – flying 200 (flying start) – 11.200 s – 50×15", "10"]


def test_mrc_is_in_percent_and_needs_an_ftp_only_for_watts():
    header, points, _ = _course(_export(ExportFormat.MRC, ftp_w=250))
    assert "MINUTES PERCENT" in header and not any(line.startswith("FTP") for line in header)
    assert points[:2] == [(0, 50), (10, 70)] and points[10][1] == 48

    no_watts = [step for step in STEPS if step.get("type") != "repeat"]
    assert _course(_export(ExportFormat.MRC, no_watts))[1][:2] == [(0, 50), (10, 70)]
    with pytest.raises(NeedsFtp):
        _export(ExportFormat.MRC)
    with pytest.raises(NeedsFtp):
        _export(ExportFormat.ERG, no_watts)
    # Watts only, nothing to convert: no FTP needed.
    assert _course(_export(ExportFormat.ERG, [{"duration_s": 60, "power": {"unit": "watts", "low": 300}}]))[1] == [(0, 300), (1, 300)]


def test_file_names_are_plain_ascii():
    assert file_stem("Sprints lancés 3×200 !") == "sprints-lances-3-200"
    assert file_stem("★★") == "workout"


# --- routes --------------------------------------------------------------------------------


@pytest.fixture
def _no_presets(monkeypatch):
    monkeypatch.setattr("app.workouts.service.presets", lambda: {})


async def test_a_library_workout_downloads_with_my_ftp(client, db_session, _no_presets):
    athlete_id = await _setup(client, db_session, upload=False)
    workout = (await client.post("/workouts", json={"name": "Flying 200s", "steps": STEPS})).json()
    url = f"/workouts/{workout['id']}/export"

    # No FTP yet: the % formats work, ERG can't convert.
    fit = await client.get(f"{url}/fit")
    assert fit.status_code == 200 and fit.headers["content-type"] == "application/vnd.ant.fit"
    assert fit.headers["content-disposition"] == 'attachment; filename="flying-200s.fit"'
    assert (await client.get(f"{url}/zwo")).status_code == 200
    assert (await client.get(f"{url}/erg")).status_code == 409
    assert (await client.get(f"{url}/gpx")).status_code == 422

    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-01-01", "ftp_w": 250})
    erg = await client.get(f"{url}/erg", params={"athlete_id": athlete_id})
    assert erg.status_code == 200 and "FTP = 250" in erg.text
    # French cues for a French-speaking viewer (the default).
    assert "départ lancé" in (await client.get(f"{url}/zwo")).text

    async with _other_client() as stranger:
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(f"{url}/fit")).status_code == 404
        assert (await stranger.get(f"{url}/fit", params={"athlete_id": athlete_id})).status_code == 403


async def test_a_planned_workout_uses_the_ftp_on_its_date(client, db_session, _no_presets):
    athlete_id = await _setup(client, db_session, upload=False)
    plans = f"/athletes/{athlete_id}/planned-sessions"
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-01-01", "ftp_w": 250})
    later = date.today() + timedelta(days=30)
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": later.isoformat(), "ftp_w": 300})

    soon = (await client.post(plans, json={"planned_date": date.today().isoformat(), "title": "Openers", "workout": STEPS})).json()
    far = (await client.post(plans, json={"planned_date": later.isoformat(), "title": "Openers", "workout": STEPS})).json()
    assert "FTP = 250" in (await client.get(f"{plans}/{soon['id']}/export/erg")).text
    assert "FTP = 300" in (await client.get(f"{plans}/{far['id']}/export/erg")).text

    bare = (await client.post(plans, json={"planned_date": later.isoformat(), "title": "Free ride"})).json()
    assert (await client.get(f"{plans}/{bare['id']}/export/fit")).status_code == 404

    # The coach reads the plan, so they may download it too; a stranger may not.
    async with _coach_of(db_session, athlete_id) as coach:
        assert (await coach.get(f"{plans}/{soon['id']}/export/fit")).status_code == 200
    async with _other_client() as stranger:
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(f"{plans}/{soon['id']}/export/fit")).status_code == 403


async def test_a_track_step_lasts_the_athletes_best(client, db_session, _no_presets):
    athlete_id = await _setup(client, db_session, upload=False)
    track_id = (await client.get(f"/athletes/{athlete_id}/tracks")).json()[0]["id"]
    body = {"event_key": "1km", "start_type": "standing", "time_ms": 70_000, "achieved_on": "2026-06-01", "track_id": track_id}
    assert (await client.post(f"/athletes/{athlete_id}/manual-results", json=body)).status_code == 201
    workout = (await client.post("/workouts", json={"name": "Kilo", "steps": [{"event_key": "1km", "start_type": "standing"}]})).json()

    zwo = ET.fromstring((await client.get(f"/workouts/{workout['id']}/export/zwo")).content)
    assert zwo.find("workout")[0].get("Duration") == "70"

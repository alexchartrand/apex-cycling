"""Planned vs ridden: the matcher on its own, then through the API."""

from app.planning.matching import EffortResults, RepStatus, expand_reps, match_reps
from app.training.efforts import StartType
from tests.test_aero_api import _setup
from tests.test_planning import _plan

S, F = StartType.STANDING, StartType.FLYING


def _targets(*items: dict) -> list[dict]:
    return list(items)


def _effort(index: int, **times: tuple[StartType, int]) -> EffortResults:
    return EffortResults(index, {(key, start): ms for key, (start, ms) in times.items()})


def test_reps_expand_in_plan_order():
    reps = expand_reps(
        _targets(
            {"label": "Openers", "reps": 2, "event_key": "500m", "start_type": "standing", "target_time_ms": 34_000},
            {"label": "Tempo"},
        )
    )
    assert [(r.target_index, r.rep, r.event_key) for r in reps] == [(0, 1, "500m"), (0, 2, "500m"), (1, 1, None)]
    assert reps[0].start_type == S and reps[0].target_time_ms == 34_000


def test_a_rep_that_needs_no_effort_is_free_and_does_not_move_the_cursor():
    reps = expand_reps(_targets({"label": "Easy"}, {"label": "Kilo", "event_key": "1km", "target_time_ms": 70_000}))
    outcomes = match_reps(reps, [_effort(1, **{"1km": (F, 69_000)})])
    assert [o.status for o in outcomes] == [RepStatus.FREE, RepStatus.HIT]
    assert outcomes[1].effort_index == 1 and outcomes[1].delta_ms == -1000


def test_efforts_that_dont_answer_are_passed_over():
    reps = expand_reps(
        _targets({"label": "Starts", "reps": 2, "event_key": "500m", "start_type": "standing", "target_time_ms": 35_000})
    )
    efforts = [
        _effort(1, **{"500m": (F, 31_000)}),  # warm-up, flying
        _effort(2, **{"500m": (S, 34_000)}),
        _effort(3, **{"500m": (S, 36_000)}),
    ]
    first, second = match_reps(reps, efforts)
    assert (first.effort_index, first.status) == (2, RepStatus.HIT)
    assert (second.effort_index, second.status, second.delta_ms) == (3, RepStatus.MISS, 1000)


def test_an_effort_answers_only_one_rep():
    reps = expand_reps(_targets({"label": "Kilo", "reps": 2, "event_key": "1km", "target_time_ms": 70_000}))
    first, second = match_reps(reps, [_effort(1, **{"1km": (F, 70_000)})])
    assert first.status is RepStatus.HIT  # exactly on target counts
    assert second.status is RepStatus.NOT_RIDDEN and second.effort_index is None


def test_without_a_target_or_a_start_the_fastest_start_answers():
    reps = expand_reps(_targets({"label": "Laps", "event_key": "lap"}))
    outcome = match_reps(reps, [_effort(1, **{"lap": (F, 18_000)})])[0]
    assert outcome.status is RepStatus.RIDDEN and outcome.time_ms == 18_000 and outcome.delta_ms is None

    reps = expand_reps(_targets({"label": "500", "event_key": "500m"}))
    both = EffortResults(1, {("500m", S): 35_000, ("500m", F): 32_000})
    assert match_reps(reps, [both])[0].start_type == F


async def test_the_comparison_endpoint_scores_each_rep(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    url = f"/athletes/{athlete_id}/planned-sessions"
    # The session: three flying 6-lap efforts, laps of 20 s, 17.5 s and 16 s on 250 m.
    plan = (
        await client.post(
            url,
            json=_plan(
                targets=[
                    {"label": "Kilos", "reps": 2, "event_key": "1km", "start_type": "flying", "target_time_ms": 75_000},
                    {"label": "Half", "event_key": "500m", "target_time_ms": 33_000},
                    {"label": "Jog"},
                    {"label": "Start", "event_key": "500m", "start_type": "standing", "target_time_ms": 35_000},
                ]
            ),
        )
    ).json()

    assert (await client.get(f"{url}/{plan['id']}/comparison")).status_code == 409  # nothing linked yet
    await client.put(f"{url}/{plan['id']}/session", json={"external_event_id": "evt-aero"})

    body = (await client.get(f"{url}/{plan['id']}/comparison")).json()
    rows = [(r["label"], r["rep"], r["status"], r["effort_index"], r["time_ms"], r["delta_ms"]) for r in body["reps"]]
    assert rows == [
        ("Kilos", 1, "miss", 1, 80_000, 5_000),
        ("Kilos", 2, "hit", 2, 70_000, -5_000),
        ("Half", 1, "hit", 3, 32_000, -1_000),
        ("Jog", 1, "free", None, None, None),
        ("Start", 1, "not_ridden", None, None, None),
    ]
    assert body["measured"] == 4 and body["hits"] == 2

    assert (await client.get(f"{url}/00000000-0000-0000-0000-000000000000/comparison")).status_code == 404

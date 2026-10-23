import uuid
from datetime import date, datetime, timedelta, timezone

from app.training.efforts import CheckpointCrossing, LapInput, StartType, detect_efforts
from app.training.insights import (
    EffortFacts,
    InsightKind,
    best_nth_lap_insights,
    broken_milestone_ms,
    derive_insights,
    lap_time_cv_pct,
    milestone_step_ms,
    most_consistent_insights,
    result_insights,
)
from app.training.records import Result
from tests.test_records import _athlete_with_fixture

_TRACK = uuid.uuid4()


def _result(day: date, time_ms: int, *, event_key="500m", start=StartType.STANDING, event_id=None, lap_id=None) -> Result:
    return Result(
        track_id=_TRACK,
        event_key=event_key,
        start_type=start,
        time_ms=time_ms,
        training_event_id=event_id or uuid.uuid4(),
        event_date=day,
        lap_id=lap_id or uuid.uuid4(),
        achieved_at=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
    )


def _effort_facts(day: date, totals: list[int | None], *, event_id=None, hour=10, flying=False) -> EffortFacts:
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=hour)
    laps, cursor = [], 0
    for total in totals:
        laps.append(
            LapInput(
                lap_id=uuid.uuid4(),
                start_time=start + timedelta(milliseconds=cursor),
                from_start=not flying,
                crossings=(CheckpointCrossing(uuid.uuid4(), "Finish", total),),
            )
        )
        cursor += total or 0
    [effort] = detect_efforts(laps, 250)
    return EffortFacts(event_id or uuid.uuid4(), _TRACK, day, effort)


# --- milestones ------------------------------------------------------------


def test_milestone_step_scales_with_the_time():
    assert [milestone_step_ms(t) for t in (19_000, 59_999, 60_000, 299_999, 300_000)] == [1_000, 1_000, 5_000, 5_000, 10_000]


def test_broken_milestone_is_the_round_time_just_above_the_new_time():
    assert broken_milestone_ms(20_400, 19_800) == 20_000
    assert broken_milestone_ms(21_300, 19_800) == 20_000  # crossed 21 and 20: the tighter one
    assert broken_milestone_ms(20_000, 19_900) == 20_000  # 20.000 isn't under 20
    assert broken_milestone_ms(19_900, 19_400) is None  # same whole second
    assert broken_milestone_ms(72_000, 69_000) == 70_000  # five-second steps above a minute


# --- records and season bests ------------------------------------------------


def test_a_first_result_is_not_a_record():
    assert result_insights([_result(date(2026, 3, 1), 40_000)]) == []


def test_personal_record_names_the_previous_best_and_the_milestone():
    results = [_result(date(2026, 3, 1), 40_400), _result(date(2026, 3, 8), 39_700)]
    [insight] = result_insights(results)
    assert (insight.kind, insight.time_ms, insight.previous_ms, insight.milestone_ms) == (
        InsightKind.PERSONAL_RECORD, 39_700, 40_400, 40_000,
    )
    assert insight.training_event_id == results[1].training_event_id


def test_season_best_needs_an_earlier_result_in_the_same_year_and_is_not_a_record():
    results = [
        _result(date(2025, 6, 1), 38_000),  # last year's best: still the record
        _result(date(2026, 3, 1), 41_000),
        _result(date(2026, 4, 1), 40_000),  # beats this season only
        _result(date(2026, 5, 1), 40_500),  # worse: no headline
    ]
    [insight] = result_insights(results)
    assert (insight.kind, insight.time_ms, insight.previous_ms) == (InsightKind.SEASON_BEST, 40_000, 41_000)
    assert insight.event_date == date(2026, 4, 1)


def test_the_first_result_of_a_new_season_is_not_a_season_best():
    assert result_insights([_result(date(2025, 6, 1), 38_000), _result(date(2026, 3, 1), 39_000)]) == []


def test_standing_and_flying_and_events_are_tracked_apart():
    results = [
        _result(date(2026, 3, 1), 40_000),
        _result(date(2026, 3, 8), 39_000, start=StartType.FLYING),
        _result(date(2026, 3, 8), 80_000, event_key="1km"),
    ]
    assert result_insights(results) == []


# --- best Nth lap ------------------------------------------------------------


def test_best_nth_lap_picks_the_biggest_improvement_per_session():
    earlier = _effort_facts(date(2026, 3, 1), [30_000, 25_000, 25_000, 25_000, 25_000])
    later_id = uuid.uuid4()
    # Lap 3 improves by 0.5 s, lap 4 by 1 s: only the 4th is reported.
    later = _effort_facts(date(2026, 3, 8), [30_000, 25_000, 24_500, 24_000, 25_000], event_id=later_id)
    [insight] = best_nth_lap_insights([earlier, later])
    assert (insight.kind, insight.lap_number, insight.time_ms, insight.previous_ms) == (InsightKind.BEST_NTH_LAP, 4, 24_000, 25_000)
    assert insight.training_event_id == later_id
    assert insight.effort_start_type == StartType.STANDING


def test_best_nth_lap_ignores_other_seasons_short_efforts_excluded_laps_and_celebrated_laps():
    last_year = _effort_facts(date(2025, 3, 1), [30_000, 25_000, 25_000, 25_000, 25_000])
    this_year = _effort_facts(date(2026, 3, 8), [30_000, 24_000, 24_000, 24_000, 24_000])
    assert best_nth_lap_insights([last_year, this_year]) == []  # nothing earlier this season

    first = _effort_facts(date(2026, 3, 1), [30_000, 25_000, 25_000, 25_000, 25_000])
    short = _effort_facts(date(2026, 3, 8), [30_000, 20_000, 20_000])  # under MIN_EFFORT_LAPS
    assert best_nth_lap_insights([first, short]) == []

    faster = _effort_facts(date(2026, 3, 9), [30_000, 24_000, 24_000, 24_000, 24_000])
    skipped = frozenset(lap.lap_id for lap in faster.effort.laps)
    assert best_nth_lap_insights([first, faster], skip_lap_ids=skipped) == []
    assert best_nth_lap_insights([first, faster])  # but reported otherwise


# --- consistency -------------------------------------------------------------


def test_lap_time_cv_skips_a_standing_start_lap_and_gives_up_on_holes():
    even = _effort_facts(date(2026, 3, 1), [30_000, 25_000, 25_000, 25_000, 25_000]).effort
    assert lap_time_cv_pct(even) == (0.0, 4)
    holed = _effort_facts(date(2026, 3, 1), [30_000, 25_000, None]).effort
    assert lap_time_cv_pct(holed) is None


def test_most_consistent_effort_must_beat_every_comparable_earlier_one():
    uneven = _effort_facts(date(2026, 3, 1), [30_000, 24_000, 26_000, 24_000, 26_000])
    steadier_id = uuid.uuid4()
    steadier = _effort_facts(date(2026, 3, 8), [30_000, 25_000, 25_200, 24_900, 25_100], event_id=steadier_id)
    unsteady = _effort_facts(date(2026, 3, 15), [30_000, 23_000, 27_000, 23_000, 27_000])
    [insight] = most_consistent_insights([uneven, steadier, unsteady])
    assert insight.kind == InsightKind.MOST_CONSISTENT
    assert insight.training_event_id == steadier_id
    assert insight.lap_count == 4
    assert 0 < insight.cv_pct < 1


def test_consistency_is_only_compared_between_similar_lap_counts():
    long_even = _effort_facts(date(2026, 3, 1), [30_000] + [25_000] * 16)  # perfectly even, 16 laps
    short = _effort_facts(date(2026, 3, 8), [30_000, 25_000, 25_200, 24_900, 25_100])  # 4 laps
    assert most_consistent_insights([long_even, short]) == []


def test_derive_orders_newest_session_first_and_most_notable_kind_first():
    results = [
        _result(date(2026, 3, 1), 41_000),
        _result(date(2026, 3, 8), 40_000, event_key="1km"),
        _result(date(2026, 3, 8), 39_000),
        _result(date(2026, 4, 8), 38_000),
    ]
    insights = derive_insights(results, [])
    assert [i.event_date for i in insights] == [date(2026, 4, 8), date(2026, 3, 8)]
    keys = [i.key for i in insights]
    assert len(set(keys)) == len(keys)


# --- through the API -----------------------------------------------------------


async def test_insights_endpoints_on_the_real_export(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "insights@example.com")

    feed = (await client.get(f"/athletes/{athlete_id}/insights", params={"days": 365, "limit": 100})).json()
    assert (await client.get(f"/athletes/{athlete_id}/insights", params={"days": 1})).json() == []  # sessions are months old
    assert len(feed) == 7
    assert {i["external_event_id"] for i in feed} == {feed[0]["external_event_id"]}  # all from the newest session

    by_event = {(i["event_key"], i["start_type"]): i for i in feed if i["kind"] == "personal_record"}
    standing_500 = by_event[("500m", "standing")]
    assert (standing_500["time_ms"], standing_500["previous_ms"], standing_500["milestone_ms"]) == (47535, 51434, 48000)
    assert by_event[("1km", "standing")]["milestone_ms"] is None  # 98.082 -> 97.590: same 5 s band
    assert all(i["session_name"] and i["track_name"] and i["key"] for i in feed)
    assert len({i["key"] for i in feed}) == len(feed)

    # The headlines agree with the record history: the newest step of the chain is the PR.
    history = (
        await client.get(
            f"/athletes/{athlete_id}/records/history",
            params={"event_key": "500m", "start_type": "standing", "track_id": standing_500["track_id"]},
        )
    ).json()
    assert history[-1]["time_ms"] == standing_500["time_ms"]
    assert history[-2]["time_ms"] == standing_500["previous_ms"]

    nth = next(i for i in feed if i["kind"] == "best_nth_lap")
    assert (nth["lap_number"], nth["time_ms"], nth["previous_ms"]) == (2, 21927, 23392)

    session_id = feed[0]["external_event_id"]
    one = (await client.get(f"/athletes/{athlete_id}/sessions/{session_id}/insights")).json()
    assert one == feed
    assert (await client.get(f"/athletes/{athlete_id}/sessions/nope/insights")).json() == []


async def test_insights_are_private_to_people_with_access(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "insights-owner@example.com")
    client.cookies.clear()
    assert (await client.get(f"/athletes/{athlete_id}/insights")).status_code == 401

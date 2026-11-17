"""Activity types: guessed from the source, chosen by the athlete, and what
they change (power curve, weekly load by type)."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.activities.kinds import ActivityType, classify, source_sport
from app.activities.models import ActivityPowerCurve, ActivitySource
from tests.test_activity_metrics import START, _add_activity, _coach_of, _fit, _post_upload, _rider, uploads_dir  # noqa: F401
from tests.fit_builder import build_fit


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("cycling",), ActivityType.CYCLING),
        (("cycling", "indoor_cycling"), ActivityType.INDOOR_CYCLING),
        (("cycling/virtual_activity",), ActivityType.INDOOR_CYCLING),
        (("cycling", "track_cycling"), ActivityType.TRACK_CYCLING),
        (("cycling", "road"), ActivityType.CYCLING),
        (("training", "strength_training"), ActivityType.STRENGTH),
        (("Biking",), ActivityType.CYCLING),  # TCX
        (("Ride",), ActivityType.CYCLING),
        (("GravelRide",), ActivityType.CYCLING),
        (("VirtualRide",), ActivityType.INDOOR_CYCLING),
        (("cycling", "VirtualRide"), ActivityType.INDOOR_CYCLING),  # Intervals.icu knows better than the file
        (("TrackRide",), ActivityType.TRACK_CYCLING),
        (("WeightTraining",), ActivityType.STRENGTH),
        (("Run",), ActivityType.OTHER),
        (("running", "track"), ActivityType.OTHER),  # a running track isn't a velodrome
        ((None,), ActivityType.CYCLING),
        (("generic",), ActivityType.CYCLING),
        ((), ActivityType.CYCLING),
    ],
)
def test_classify(names, expected):
    assert classify(*names) == expected


def test_source_sport_joins_distinct_names():
    assert source_sport("cycling", "indoor_cycling") == "cycling/indoor_cycling"
    assert source_sport("cycling", "generic") == "cycling"
    assert source_sport("cycling", "Cycling") == "cycling"
    assert source_sport(None, None) is None


async def test_upload_reads_the_fit_sub_sport(client):
    athlete_id = await _rider(client)
    records = [{"t": t, "power": 200, "speed": 9.0} for t in range(120)]
    # sub-sport 6 = indoor_cycling
    (result,) = await _post_upload(client, athlete_id, build_fit(START, records, sub_sport=6))
    assert result["activity"]["sport"] == "cycling/indoor_cycling"
    assert (result["activity"]["activity_type"], result["activity"]["activity_type_manual"]) == ("indoor_cycling", False)


async def test_athlete_sets_and_resets_the_type(client, db_session):
    athlete_id = await _rider(client)
    (result,) = await _post_upload(client, athlete_id, _fit())
    url = f"/athletes/{athlete_id}/activities/{result['activity']['id']}"
    assert result["activity"]["activity_type"] == "cycling"

    changed = (await client.patch(url, json={"activity_type": "indoor_cycling", "name": "Trainer"})).json()
    assert (changed["activity_type"], changed["activity_type_manual"], changed["name"]) == ("indoor_cycling", True, "Trainer")
    assert (await client.patch(url, json={"activity_type": "swimming"})).status_code == 422
    # Changing something else keeps the choice.
    assert (await client.patch(url, json={"rpe": 4})).json()["activity_type"] == "indoor_cycling"

    reset = (await client.patch(url, json={"activity_type": None})).json()
    assert (reset["activity_type"], reset["activity_type_manual"]) == ("cycling", False)

    async with _coach_of(db_session, athlete_id) as coach:
        assert (await coach.patch(url, json={"activity_type": "strength"})).status_code == 403


async def test_list_filters_by_type(client, db_session):
    athlete_id = await _rider(client)
    ride = await _add_activity(db_session, athlete_id, START)
    gym = await _add_activity(db_session, athlete_id, START + timedelta(days=1), activity_type="strength")
    url = f"/athletes/{athlete_id}/activities"
    assert [a["id"] for a in (await client.get(url, params={"type": "strength"})).json()] == [str(gym)]
    both = (await client.get(url, params=[("type", "strength"), ("type", "cycling")])).json()
    assert {a["id"] for a in both} == {str(ride), str(gym)}


async def test_power_curve_counts_only_rides(client, db_session):
    athlete_id = await _rider(client)
    ride = await _add_activity(db_session, athlete_id, START, has_power=True)
    gym = await _add_activity(db_session, athlete_id, START, has_power=True, activity_type="strength", elapsed_s=60)
    async with db_session() as session:
        session.add_all(
            [
                ActivityPowerCurve(activity_id=ride, duration_s=5, power_w=900),
                ActivityPowerCurve(activity_id=gym, duration_s=5, power_w=1500),
            ]
        )
        await session.commit()
    curve = (await client.get(f"/athletes/{athlete_id}/power-curve")).json()
    assert [(p["power_w"], p["activity_id"]) for p in curve] == [(900, str(ride))]


async def test_weekly_load_by_type(client, db_session):
    from app.training.models import TrainingEvent
    import uuid

    athlete_id = await _rider(client)
    # Week of Mon June 1: an hour's ride at RPE 5, a 30 min gym session unrated.
    # Week of June 8: a 2 h sqorz session rated 6, and a Strava ride (owner-only).
    await _add_activity(db_session, athlete_id, datetime(2026, 6, 2, 12, tzinfo=timezone.utc), rpe=5)
    await _add_activity(
        db_session, athlete_id, datetime(2026, 6, 3, 12, tzinfo=timezone.utc), activity_type="strength", elapsed_s=1800, moving_s=1800
    )
    await _add_activity(
        db_session, athlete_id, datetime(2026, 6, 9, 12, tzinfo=timezone.utc), rpe=4, source=ActivitySource.STRAVA
    )
    async with db_session() as session:
        session.add(
            TrainingEvent(
                athlete_id=uuid.UUID(athlete_id),
                sqorz_account_id="acc",
                external_event_id="ev1",
                name="Track night",
                event_date=date(2026, 6, 10),
                start_timestamp=datetime(2026, 6, 10, 22, tzinfo=timezone.utc),
                end_timestamp=datetime(2026, 6, 11, 0, tzinfo=timezone.utc),
                rpe=6,
            )
        )
        await session.commit()
    params = {"through": "2026-06-12", "weeks": 3}

    weeks = (await client.get(f"/athletes/{athlete_id}/training-load/weekly", params=params)).json()
    assert [w["week_start"] for w in weeks] == ["2026-05-25", "2026-06-01", "2026-06-08"]
    assert weeks[0]["types"] == []
    first = {t["activity_type"]: t for t in weeks[1]["types"]}
    assert first["cycling"]["seconds"] == 3600 and first["cycling"]["tss"] > 0
    assert first["strength"] == {"activity_type": "strength", "seconds": 1800, "tss": 0}
    second = {t["activity_type"]: t for t in weeks[2]["types"]}
    assert second["track_cycling"]["seconds"] == 7200 and second["track_cycling"]["tss"] > 0
    assert second["cycling"]["seconds"] == 3600

    async with _coach_of(db_session, athlete_id) as coach:
        theirs = (await coach.get(f"/athletes/{athlete_id}/training-load/weekly", params=params)).json()
    assert {t["activity_type"] for t in theirs[2]["types"]} == {"track_cycling"}  # no Strava for a coach

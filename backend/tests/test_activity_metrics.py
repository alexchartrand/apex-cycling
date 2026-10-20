import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.activities import metrics_service
from app.activities.models import Activity, ActivityPowerCurve, ActivitySource
from app.analysis import metrics
from app.athletes.models import CoachAthlete, CoachAthleteStatus
from app.core.config import get_settings
from app.main import app as real_app
from app.training.models import TrainingEvent
from tests.fit_builder import build_fit
from tests.test_account import _signup

START = datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


def _fit(start: datetime = START, seconds: int = 600, power: int | None = 250, spike: int | None = None) -> bytes:
    records = []
    for t in range(seconds):
        record = {"t": t, "heart_rate": 140, "speed": 10.0, "distance": 10.0 * t}
        if power is not None:
            record["power"] = spike if spike is not None and t == 100 else power
        records.append(record)
    return build_fit(start, records)


def _upload(athlete_id: str, *contents: bytes):
    return {"url": f"/athletes/{athlete_id}/activities/upload",
            "files": [("files", (f"{i}.fit", c, "application/octet-stream")) for i, c in enumerate(contents)]}  # fmt: skip


@asynccontextmanager
async def _coach_of(db_session, athlete_id: str):
    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as coach_client:
        coach = await _signup(coach_client, "coach@example.com")
        async with db_session() as session:
            session.add(
                CoachAthlete(
                    coach_user_id=uuid.UUID(coach["id"]), athlete_id=uuid.UUID(athlete_id), status=CoachAthleteStatus.ACTIVE
                )
            )
            await session.commit()
        yield coach_client


async def _rider(client) -> str:
    await _signup(client, "rider@example.com")
    return (await client.get("/athletes/me")).json()["id"]


async def _post_upload(client, athlete_id, *contents):
    spec = _upload(athlete_id, *contents)
    return (await client.post(spec["url"], files=spec["files"])).json()


# --- stored on import ------------------------------------------------------


async def test_import_stores_the_power_curve_and_normalized_power(client, db_session):
    athlete_id = await _rider(client)
    (result,) = await _post_upload(client, athlete_id, _fit(power=250, spike=700))

    assert result["activity"]["normalized_power_w"] > 250
    async with db_session() as session:
        curve = {c.duration_s: c.power_w for c in await session.scalars(select(ActivityPowerCurve))}
    assert curve[1] == 700
    assert curve[5] == pytest.approx((700 + 4 * 250) / 5)
    assert curve[600] == pytest.approx((599 * 250 + 700) / 600)  # all 600 samples
    assert max(curve) == 600  # nothing longer than the ride


async def test_an_activity_without_power_has_no_curve(client, db_session):
    athlete_id = await _rider(client)
    (result,) = await _post_upload(client, athlete_id, _fit(power=None))

    assert result["activity"]["normalized_power_w"] is None and result["activity"]["tss"] is None
    async with db_session() as session:
        assert (await session.scalars(select(ActivityPowerCurve))).all() == []


async def test_tss_follows_the_ftp_in_force_on_the_day(client):
    athlete_id = await _rider(client)
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-05-01", "ftp_w": 250})
    (result,) = await _post_upload(client, athlete_id, _fit(power=250))
    activity_id = result["activity"]["id"]

    # 599 s at exactly FTP.
    assert result["activity"]["tss"] == pytest.approx(599 / 3600 * 100, rel=1e-3)

    async def tss():
        return (await client.get(f"/athletes/{athlete_id}/activities/{activity_id}")).json()["tss"]

    # A later FTP doesn't touch a ride that came before it ...
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-07-01", "ftp_w": 300})
    assert await tss() == pytest.approx(599 / 3600 * 100, rel=1e-3)
    # ... a correction effective before it does.
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-05-15", "ftp_w": 200})
    assert await tss() == pytest.approx(599 / 3600 * (250 / 200) ** 2 * 100, rel=1e-3)
    # No FTP left at all: no TSS.
    metric_ids = [m["id"] for m in (await client.get(f"/athletes/{athlete_id}/metrics")).json()]
    for metric_id in metric_ids:
        await client.delete(f"/athletes/{athlete_id}/metrics/{metric_id}")
    assert await tss() is None


async def test_the_ride_lands_on_the_clubs_local_day():
    ride = datetime(2026, 6, 2, 1, 30, tzinfo=timezone.utc)  # 21:30 on June 1 in Montreal
    assert metrics_service.local_day(ride, ZoneInfo("America/Montreal")) == date(2026, 6, 1)
    assert metrics_service.local_day(ride, ZoneInfo("UTC")) == date(2026, 6, 2)


# --- editing -----------------------------------------------------------------


async def test_rename_note_and_rate_an_activity(client, db_session):
    athlete_id = await _rider(client)
    (result,) = await _post_upload(client, athlete_id, _fit(power=None))
    url = f"/athletes/{athlete_id}/activities/{result['activity']['id']}"

    resp = await client.patch(url, json={"name": "Endurance", "rpe": 4, "notes": "windy"})
    assert resp.status_code == 200
    assert (resp.json()["name"], resp.json()["rpe"], resp.json()["notes"]) == ("Endurance", 4, "windy")

    # Only what is sent changes; null clears.
    resp = await client.patch(url, json={"rpe": None})
    assert (resp.json()["name"], resp.json()["rpe"], resp.json()["notes"]) == ("Endurance", None, "windy")

    assert (await client.patch(url, json={"rpe": 11})).status_code == 422
    assert (await client.patch(url, json={"rpe": 0})).status_code == 422


async def test_a_coach_cannot_edit_an_activity(client, db_session):
    athlete_id = await _rider(client)
    (result,) = await _post_upload(client, athlete_id, _fit())
    async with _coach_of(db_session, athlete_id) as coach:
        resp = await coach.patch(f"/athletes/{athlete_id}/activities/{result['activity']['id']}", json={"rpe": 9})
        assert resp.status_code == 403


# --- training load ---------------------------------------------------------


async def _add_activity(db_session, athlete_id: str, start: datetime, **fields) -> uuid.UUID:
    async with db_session() as session:
        activity = Activity(
            athlete_id=uuid.UUID(athlete_id),
            source=fields.pop("source", ActivitySource.UPLOAD),
            start_time=start,
            elapsed_s=fields.pop("elapsed_s", 3600),
            moving_s=fields.pop("moving_s", 3600),
            **fields,
        )
        session.add(activity)
        await session.commit()
        return activity.id


async def test_training_load_mixes_power_rpe_and_rated_sessions(client, db_session):
    athlete_id = await _rider(client)
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-05-01", "ftp_w": 250})
    # June 1: a power ride (599 s at FTP). June 2: an hour at RPE 5, no power.
    # June 3: an unrated hour (adds nothing). June 4: a rated 2 h sqorz session.
    await _post_upload(client, athlete_id, _fit(power=250))
    await _add_activity(db_session, athlete_id, datetime(2026, 6, 2, 12, tzinfo=timezone.utc), rpe=5)
    await _add_activity(db_session, athlete_id, datetime(2026, 6, 3, 12, tzinfo=timezone.utc))
    async with db_session() as session:
        session.add(
            TrainingEvent(
                athlete_id=uuid.UUID(athlete_id),
                sqorz_account_id="acc",
                external_event_id="ev1",
                name="Track night",
                event_date=date(2026, 6, 4),
                start_timestamp=datetime(2026, 6, 4, 22, tzinfo=timezone.utc),
                end_timestamp=datetime(2026, 6, 5, 0, tzinfo=timezone.utc),
                rpe=6,
            )
        )
        await session.commit()

    load = (await client.get(f"/athletes/{athlete_id}/training-load", params={"through": "2026-06-06", "days": 30})).json()

    by_day = {d["day"]: d for d in load["days"]}
    assert list(by_day)[0] == "2026-06-01" and list(by_day)[-1] == "2026-06-06"
    assert by_day["2026-06-01"]["tss"] == pytest.approx(599 / 3600 * 100, rel=1e-3)
    assert by_day["2026-06-02"]["tss"] == pytest.approx(metrics.srpe_training_stress(5, 3600))
    assert by_day["2026-06-03"]["tss"] == 0
    assert by_day["2026-06-04"]["tss"] == pytest.approx(metrics.srpe_training_stress(6, 7200))
    assert load["unrated_activities"] == 1

    expected = metrics.training_load({date.fromisoformat(d): v["tss"] for d, v in by_day.items() if v["tss"]}, date(2026, 6, 6))
    assert by_day["2026-06-06"]["ctl"] == pytest.approx(expected[-1].ctl)
    assert by_day["2026-06-06"]["tsb"] == pytest.approx(expected[-2].ctl - expected[-2].atl)


async def test_training_load_window_keeps_the_history_behind_it(client, db_session):
    athlete_id = await _rider(client)
    await _add_activity(db_session, athlete_id, datetime(2026, 6, 1, 12, tzinfo=timezone.utc), rpe=7)

    load = (await client.get(f"/athletes/{athlete_id}/training-load", params={"through": "2026-06-20", "days": 5})).json()

    assert [d["day"] for d in load["days"]] == [f"2026-06-{d}" for d in range(16, 21)]
    assert all(d["tss"] == 0 for d in load["days"])
    assert load["days"][0]["ctl"] > load["days"][-1]["ctl"] > 0  # still decaying from the ride on June 1
    assert load["unrated_activities"] == 0


async def test_training_load_with_nothing_is_empty(client):
    athlete_id = await _rider(client)
    resp = await client.get(f"/athletes/{athlete_id}/training-load")
    assert resp.status_code == 200 and resp.json() == {"days": [], "unrated_activities": 0}
    assert (await client.get(f"/athletes/{athlete_id}/training-load", params={"days": 0})).status_code == 422


async def test_strava_load_is_for_its_owner(client, db_session):
    athlete_id = await _rider(client)
    await _add_activity(db_session, athlete_id, datetime(2026, 6, 1, 12, tzinfo=timezone.utc), rpe=5, source=ActivitySource.STRAVA)
    params = {"through": "2026-06-01", "days": 7}

    mine = (await client.get(f"/athletes/{athlete_id}/training-load", params=params)).json()
    assert mine["days"][-1]["tss"] > 0
    async with _coach_of(db_session, athlete_id) as coach:
        theirs = (await coach.get(f"/athletes/{athlete_id}/training-load", params=params)).json()
    assert theirs["days"] == []


# --- power curve -------------------------------------------------------------


async def test_power_curve_is_the_best_per_duration_with_its_activity(client, db_session):
    athlete_id = await _rider(client)
    june = datetime(2026, 6, 1, 7, tzinfo=timezone.utc)
    steady, sprint = await _post_upload(client, athlete_id, _fit(june, power=300), _fit(june + timedelta(days=10), power=200, spike=900))

    curve = {p["duration_s"]: p for p in (await client.get(f"/athletes/{athlete_id}/power-curve")).json()}
    assert curve[1]["power_w"] == 900 and curve[1]["activity_id"] == sprint["activity"]["id"]
    assert curve[600]["power_w"] == 300 and curve[600]["activity_id"] == steady["activity"]["id"]
    assert curve[1]["start_time"].startswith("2026-06-11")

    # A range selects which rides count.
    early = (await client.get(f"/athletes/{athlete_id}/power-curve", params={"end": "2026-06-05T00:00:00Z"})).json()
    assert {p["activity_id"] for p in early} == {steady["activity"]["id"]}
    later = (await client.get(f"/athletes/{athlete_id}/power-curve", params={"start": "2026-06-05T00:00:00Z"})).json()
    assert {p["activity_id"] for p in later} == {sprint["activity"]["id"]}


async def test_strava_power_is_not_on_a_coachs_curve(client, db_session):
    athlete_id = await _rider(client)
    activity_id = await _add_activity(db_session, athlete_id, START, source=ActivitySource.STRAVA, external_id="1")
    async with db_session() as session:
        session.add(ActivityPowerCurve(activity_id=activity_id, duration_s=5, power_w=1000))
        await session.commit()

    assert len((await client.get(f"/athletes/{athlete_id}/power-curve")).json()) == 1
    async with _coach_of(db_session, athlete_id) as coach:
        assert (await coach.get(f"/athletes/{athlete_id}/power-curve")).json() == []


async def test_recompute_rebuilds_from_the_stored_stream(client, db_session):
    athlete_id = await _rider(client)
    (result,) = await _post_upload(client, athlete_id, _fit(power=250, spike=700))
    activity_id = uuid.UUID(result["activity"]["id"])
    async with db_session() as session:
        activity = await session.get(Activity, activity_id)
        original = activity.normalized_power_w
        activity.normalized_power_w = 1.0
        await session.execute(ActivityPowerCurve.__table__.delete())
        assert await metrics_service.rebuild_power_metrics(session, activity)
        await session.commit()
        assert activity.normalized_power_w == pytest.approx(original)
        assert len((await session.scalars(select(ActivityPowerCurve))).all()) > 20

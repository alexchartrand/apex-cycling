"""CdA estimate of a sqorz session from its linked recording's power."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.activities.models import Activity, ActivitySource
from app.analysis import physics
from app.athletes.models import AthleteMetric
from app.connections.service import create_transponder_assignment
from app.core.config import get_settings
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.training.models import Track
from tests.fit_builder import build_fit
from tests.test_account import _signup
from tests.test_activity_fusion import _coach_of, _upload
from tests.test_training import _epoch_ms, _track_payload

START = datetime(2026, 6, 12, 18, 0, tzinfo=timezone.utc)
TRANSPONDER = "TP-AERO"
RIDER_KG, BIKE_KG = 74.0, 8.0
CDA, CRR = 0.23, 0.003
RHO = physics.air_density(20.0, elevation_m=0.0, humidity_pct=50.0)
# Three efforts at different speeds, a minute apart.
EFFORTS = [[20.0] * 6, [17.5] * 6, [16.0] * 6]
GAP_S = 60.0


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


def _laps() -> list[tuple[float, float]]:
    """(seconds after START, lap time) of every lap."""
    laps, clock = [], 0.0
    for effort in EFFORTS:
        for duration in effort:
            laps.append((clock, duration))
            clock += duration
        clock += GAP_S
    return laps


def _payload() -> dict:
    laps = [
        {
            "lapId": f"aero-lap{i}",
            "trackId": "trk1",
            "classCode": "A",
            "startTime": _epoch_ms(START + timedelta(seconds=offset)),
            "lapTimes": [round(duration * 300), round(duration * 650), round(duration * 1000)],
            "fromStart": True,
            "startNumber": 1,
        }
        for i, (offset, duration) in enumerate(_laps())
    ]
    return {
        "transponderCode": TRANSPONDER,
        "eventTrainingDetails": [
            {
                "accountId": "acc-1",
                "accountName": "TestClub",
                "cacheSeconds": 60,
                "trainingDetail": {
                    "eventId": "evt-aero",
                    "eventName": "Aero night",
                    "eventDate": START.date().isoformat(),
                    "sportType": "track",
                    "classes": [{"classCode": "A", "className": "Open", "classType": "open"}],
                    "tracks": [_track_payload()],
                    "members": [{"classCode": "A", "transponder": TRANSPONDER, "trainingLaps": laps}],
                    "groups": [],
                    "lowBatteryTransponders": [],
                    "maxTrainingHours": 24,
                    "startTimestamp": START.isoformat().replace("+00:00", "Z"),
                    "endTimestamp": (START + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                },
            }
        ],
    }


def _recording() -> bytes:
    """Power from the physics model at each lap's speed; easy riding between."""
    setup = physics.Setup(mass_kg=RIDER_KG + BIKE_KG, cda_m2=CDA, rho=RHO, crr=CRR)
    laps = _laps()
    lead = 60
    records = []
    for t in range(lead + int(laps[-1][0] + laps[-1][1]) + 60):
        into = t - lead
        lap = next((d for s, d in laps if s <= into < s + d), None)
        speed = 250 / lap if lap else 6.0
        power = physics.power_required_w(speed, setup) if lap else 80
        records.append({"t": t, "power": round(power), "speed": speed, "heart_rate": 150, "cadence": 100})
    return build_fit(START - timedelta(seconds=lead), records)


async def _setup(client, db_session, *, length_m: float | None = 250.0, weight: bool = True, upload: bool = True) -> str:
    user = await _signup(client, "aero@example.com")
    athlete_id = (await client.get("/athletes/me")).json()["id"]
    async with db_session() as session:
        await create_transponder_assignment(
            session,
            athlete_id=uuid.UUID(athlete_id),
            transponder_code=TRANSPONDER,
            start_date=date(2026, 6, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user["id"]),
            notes=None,
        )
        await normalize_snapshot(session, _payload())
        await session.execute(update(Track).values(length_m=length_m))
        if weight:
            session.add(AthleteMetric(athlete_id=uuid.UUID(athlete_id), effective_date=date(2026, 7, 1), weight_kg=RIDER_KG))
        await session.commit()
    if upload:
        activity = await _upload(client, athlete_id, _recording())
        assert activity["external_event_id"] == "evt-aero"
    return athlete_id


async def test_estimates_cda_and_crr_from_the_session(client, db_session):
    athlete_id = await _setup(client, db_session)
    resp = await client.post(f"/athletes/{athlete_id}/sessions/evt-aero/aero", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["problem"] is None
    assert body["track_name"] == "Test Track" and body["track_length_m"] == 250
    conditions = body["conditions"]
    assert conditions["rho"] == pytest.approx(RHO)
    # The only weigh-in is after the session: it's still the best guess.
    assert conditions["rider_kg"] == RIDER_KG and conditions["rider_kg_date"] == "2026-07-01"
    assert conditions["bike_kg"] == BIKE_KG

    points = body["points"]
    assert len(points) == 18
    assert [p["effort_index"] for p in points] == [1] * 6 + [2] * 6 + [3] * 6
    assert [p["issue"] for p in points if p["lap_in_effort"] == 1] == ["first_lap"] * 3
    fit = body["fit"]
    assert fit["laps_used"] == 15
    assert fit["crr_source"] == "fitted"
    assert fit["cda_m2"] == pytest.approx(CDA, abs=0.005)
    assert fit["crr"] == pytest.approx(CRR, abs=0.0005)
    assert fit["r_squared"] > 0.99


async def test_inputs_and_a_lap_selection_change_the_estimate(client, db_session):
    athlete_id = await _setup(client, db_session)
    url = f"/athletes/{athlete_id}/sessions/evt-aero/aero"
    points = (await client.post(url, json={})).json()["points"]
    fastest = [p["lap_id"] for p in points if p["effort_index"] == 3]

    body = (await client.post(url, json={"lap_ids": fastest, "crr": CRR})).json()
    assert [p["used"] for p in body["points"]] == [False] * 12 + [True] * 6  # its first lap too: chosen by hand
    assert body["fit"]["crr_source"] == "given" and body["fit"]["laps_used"] == 6
    assert body["fit"]["cda_m2"] == pytest.approx(CDA, abs=0.01)

    same_crr = (await client.post(url, json={"crr": CRR})).json()
    heavier = (await client.post(url, json={"rider_kg": 90, "bike_kg": 9, "crr": CRR})).json()
    assert heavier["conditions"]["rider_kg"] == 90 and heavier["conditions"]["rider_kg_date"] is None
    # 17 kg more rolling resistance (~0.5 N) explains part of the power, so less is left for drag.
    assert heavier["fit"]["cda_m2"] == pytest.approx(same_crr["fit"]["cda_m2"] - 0.004, abs=0.001)

    warm = (await client.post(url, json={"temp_c": 35, "pressure_hpa": 950})).json()
    assert warm["conditions"]["rho"] == pytest.approx(physics.air_density(35, pressure_pa=95_000, humidity_pct=50))


async def test_tells_what_is_missing(client, db_session):
    athlete_id = await _setup(client, db_session, length_m=None, weight=False, upload=False)
    url = f"/athletes/{athlete_id}/sessions/evt-aero/aero"
    body = (await client.post(url, json={})).json()
    assert body["problem"] == "no_track_length" and body["points"] == [] and body["fit"] is None

    async with db_session() as session:
        await session.execute(update(Track).values(length_m=250.0))
        await session.commit()
    assert (await client.post(url, json={})).json()["problem"] == "no_weight"
    body = (await client.post(url, json={"rider_kg": 70})).json()
    assert body["problem"] == "no_power" and len(body["points"]) == 18
    assert all(p["issue"] == "no_power" for p in body["points"])


async def test_unknown_session_or_track(client, db_session):
    athlete_id = await _setup(client, db_session, upload=False)
    assert (await client.post(f"/athletes/{athlete_id}/sessions/nope/aero", json={})).status_code == 404
    resp = await client.post(f"/athletes/{athlete_id}/sessions/evt-aero/aero", json={"track_id": str(uuid.uuid4())})
    assert resp.status_code == 404


async def test_a_coach_never_gets_an_estimate_from_strava_power(client, db_session):
    athlete_id = await _setup(client, db_session)
    async with db_session() as session:
        await session.execute(update(Activity).values(source=ActivitySource.STRAVA, external_id="s-1"))
        await session.commit()
    url = f"/athletes/{athlete_id}/sessions/evt-aero/aero"
    assert (await client.post(url, json={})).json()["fit"] is not None
    async with _coach_of(db_session, athlete_id) as coach:
        theirs = (await coach.post(url, json={})).json()
        assert theirs["problem"] == "no_power" and theirs["fit"] is None
        assert all(p["power_w"] is None for p in theirs["points"])
    async with db_session() as session:
        assert (await session.scalar(select(Activity))).training_event_id is not None

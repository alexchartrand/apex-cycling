from datetime import date

from httpx import ASGITransport, AsyncClient

from app.athletes.models import AthleteMetric
from app.athletes.service import metrics_as_of
from app.main import app as real_app


async def _signup(client, email, **extra):
    resp = await client.post(
        "/auth/signup",
        json={"email": email, "password": "Correcthorse123!", "display_name": "Rider", **extra},
    )
    assert resp.status_code == 201
    return resp.json()


async def _my_athlete_id(client) -> str:
    return (await client.get("/athletes/me")).json()["id"]


async def test_update_profile_fields_and_category(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _my_athlete_id(client)

    resp = await client.patch(
        f"/athletes/{athlete_id}",
        json={"display_name": "Marie", "birthdate": "1990-05-02", "sex": "female", "height_cm": 168.5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Marie"
    assert body["sex"] == "female"
    assert body["height_cm"] == 168.5
    assert body["category"].startswith("M")

    # Partial update: absent fields are kept, explicit null clears.
    resp = await client.patch(f"/athletes/{athlete_id}", json={"height_cm": None})
    body = resp.json()
    assert body["height_cm"] is None
    assert body["display_name"] == "Marie"
    assert body["birthdate"] == "1990-05-02"


async def test_update_profile_validates(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _my_athlete_id(client)

    for payload in ({"display_name": None}, {"display_name": ""}, {"sex": "x"}, {"height_cm": 20}, {"birthdate": "2999-01-01"}):
        resp = await client.patch(f"/athletes/{athlete_id}", json=payload)
        assert resp.status_code == 422, payload


async def test_cannot_update_someone_elses_profile(client, db_session):
    await _signup(client, "owner@example.com")
    owner_athlete_id = await _my_athlete_id(client)

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as other:
        await _signup(other, "stranger@example.com")
        assert (await other.patch(f"/athletes/{owner_athlete_id}", json={"display_name": "Hacked"})).status_code == 403
        assert (await other.get(f"/athletes/{owner_athlete_id}/metrics")).status_code == 403


async def test_record_list_and_merge_metrics(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _my_athlete_id(client)

    resp = await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-01-10", "weight_kg": 72.4})
    assert resp.status_code == 201
    first_id = resp.json()["id"]

    # Same date again: merged into the same row, existing weight untouched.
    resp = await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-01-10", "ftp_w": 280})
    assert resp.json()["id"] == first_id
    assert resp.json()["weight_kg"] == 72.4
    assert resp.json()["ftp_w"] == 280

    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-03-01", "weight_kg": 71.0})

    rows = (await client.get(f"/athletes/{athlete_id}/metrics")).json()
    assert [r["effective_date"] for r in rows] == ["2026-03-01", "2026-01-10"]


async def test_metrics_require_a_value(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _my_athlete_id(client)
    resp = await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-01-10"})
    assert resp.status_code == 422


async def test_current_metrics_as_of_a_date(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _my_athlete_id(client)
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-01-10", "weight_kg": 72.4, "ftp_w": 280})
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-03-01", "weight_kg": 71.0})

    body = (await client.get(f"/athletes/{athlete_id}/metrics/current", params={"on": "2026-02-01"})).json()
    assert body["weight_kg"] == {"value": 72.4, "effective_date": "2026-01-10"}
    assert body["ftp_w"] == {"value": 280, "effective_date": "2026-01-10"}
    assert body["max_hr"] is None

    body = (await client.get(f"/athletes/{athlete_id}/metrics/current", params={"on": "2026-03-01"})).json()
    assert body["weight_kg"]["value"] == 71.0
    # FTP carries forward from the older row.
    assert body["ftp_w"]["effective_date"] == "2026-01-10"

    body = (await client.get(f"/athletes/{athlete_id}/metrics/current", params={"on": "2025-12-31"})).json()
    assert body["weight_kg"] is None


async def test_delete_metric(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = await _my_athlete_id(client)
    metric_id = (
        await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-01-10", "weight_kg": 72})
    ).json()["id"]

    assert (await client.delete(f"/athletes/{athlete_id}/metrics/{metric_id}")).status_code == 204
    assert (await client.get(f"/athletes/{athlete_id}/metrics")).json() == []
    assert (await client.delete(f"/athletes/{athlete_id}/metrics/{metric_id}")).status_code == 404


def test_metrics_as_of_tracks_fields_independently():
    rows = [
        AthleteMetric(effective_date=date(2026, 2, 1), weight_kg=70.0),
        AthleteMetric(effective_date=date(2026, 1, 1), weight_kg=72.0, max_hr=195),
        AthleteMetric(effective_date=date(2026, 3, 1), max_hr=190),
    ]
    values = metrics_as_of(rows, date(2026, 2, 15))
    assert values["weight_kg"].value == 70.0
    assert values["max_hr"].value == 195
    assert values["ftp_w"] is None


async def test_preferences_default_update_and_signup_locale(client, db_session):
    user = await _signup(client, "rider@example.com", locale="fr")
    assert user["locale"] == "fr"
    assert user["theme"] is None

    resp = await client.patch("/auth/me/preferences", json={"theme": "dark"})
    assert resp.status_code == 200
    assert resp.json() == {**user, "theme": "dark"}

    resp = await client.patch("/auth/me/preferences", json={"locale": None})
    assert resp.json()["locale"] is None
    assert resp.json()["theme"] == "dark"

    for payload in ({"theme": "sepia"}, {"locale": "de"}):
        assert (await client.patch("/auth/me/preferences", json=payload)).status_code == 422, payload

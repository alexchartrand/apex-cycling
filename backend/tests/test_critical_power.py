from datetime import datetime, timedelta, timezone

import pytest

from app.analysis.critical_power import fit_critical_power, predicted_power, suggest_ftp, worth_suggesting
from app.core.config import get_settings
from tests.fit_builder import build_fit
from tests.test_account import _signup

DURATIONS = (180, 300, 480, 720, 1200)


def _curve(cp: float, w_prime: float, durations=DURATIONS):
    return [(t, cp + w_prime / t) for t in durations]


def test_fit_recovers_cp_and_w_prime_from_an_exact_curve():
    fit = fit_critical_power(_curve(300, 20_000))
    assert fit is not None
    assert fit.cp_w == pytest.approx(300)
    assert fit.w_prime_j == pytest.approx(20_000)
    assert fit.r_squared == pytest.approx(1)
    assert fit.points == 5
    assert predicted_power(fit, 600) == pytest.approx(300 + 20_000 / 600)


def test_fit_ignores_efforts_outside_the_band():
    # A 10 s sprint and a 3 h ride are not on the CP line; they must not bend it.
    curve = _curve(280, 18_000) + [(10, 1400.0), (10_800, 150.0)]
    fit = fit_critical_power(curve)
    assert fit is not None and fit.cp_w == pytest.approx(280) and fit.points == 5


def test_fit_needs_short_and_long_efforts_and_enough_points():
    assert fit_critical_power(_curve(300, 20_000, (180, 300, 480))) is None  # nothing long
    assert fit_critical_power(_curve(300, 20_000, (720, 900, 1200))) is None  # nothing short
    assert fit_critical_power(_curve(300, 20_000, (300, 1200))) is None  # two points
    assert fit_critical_power([]) is None


def test_fit_rejects_an_unphysical_line():
    # Power rising with duration gives a negative slope.
    assert fit_critical_power([(300, 200.0), (600, 250.0), (1200, 300.0)]) is None
    # Work that falls with time gives a negative intercept.
    assert fit_critical_power([(300, 100.0), (600, 300.0), (1200, 500.0)]) is None


def test_ftp_suggestion_is_95_percent_of_the_best_20_minutes():
    assert suggest_ftp([(300, 350.0), (1200, 300.0), (3600, 270.0)]) == (pytest.approx(285.0), 1200)
    assert suggest_ftp([(300, 350.0), (3600, 270.0)]) is None


def test_a_suggestion_close_to_the_current_ftp_is_not_worth_a_prompt():
    assert worth_suggesting(285, None)
    assert worth_suggesting(300, 280)
    assert worth_suggesting(260, 280)  # the data can also say FTP fell
    assert not worth_suggesting(282, 280)


# --- endpoint ----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


async def test_power_profile_suggests_an_ftp_until_the_athlete_has_one(client):
    await _signup(client, "rider@example.com")
    athlete_id = (await client.get("/athletes/me")).json()["id"]
    start = datetime.now(timezone.utc) - timedelta(days=10)
    fit = build_fit(start, [{"t": t, "power": 300, "heart_rate": 140, "cadence": 90, "speed": 10.0, "distance": 10.0 * t} for t in range(1500)])
    uploaded = await client.post(
        f"/athletes/{athlete_id}/activities/upload", files=[("files", ("a.fit", fit, "application/octet-stream"))]
    )
    assert uploaded.json()[0]["status"] == "created"

    profile = (await client.get(f"/athletes/{athlete_id}/power-profile")).json()
    assert profile["ftp_current_w"] is None
    assert profile["ftp_suggestion"]["ftp_w"] == pytest.approx(285)
    assert profile["ftp_suggestion"]["source_duration_s"] == 1200
    # Flat 300 W has no short-vs-long contrast beyond the line itself: CP is the 300 W, W' ~ 0.
    assert profile["critical_power"]["cp_w"] == pytest.approx(300, abs=1)

    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-01-01", "ftp_w": 284})
    profile = (await client.get(f"/athletes/{athlete_id}/power-profile")).json()
    assert profile["ftp_current_w"] == 284
    assert profile["ftp_suggestion"] is None

    # A window that predates the ride sees no power at all.
    assert (await client.get(f"/athletes/{athlete_id}/power-profile?days=14")).status_code == 200
    assert (await client.get(f"/athletes/{athlete_id}/power-profile?days=3")).status_code == 422

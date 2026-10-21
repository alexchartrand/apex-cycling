import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.training.facility import FACILITIES_FILE, InvalidFacilityFile, import_profiles, load_profiles
from app.training.models import Track
from tests.test_track_settings import _FIXTURE, _SESSION_DATE, _athlete_with_track, _track

_ACCOUNT = "68ee5442f9df317afcb99baf"


def _entry(**changes) -> dict:
    entry = {
        "sqorz_account_id": _ACCOUNT,
        "track_name": "Bromont - CNCB",
        "localisation": {"city": "Bromont", "region": "Québec", "country": "Canada", "latitude": 45.3, "longitude": -72.7},
        "length_m": 250,
        "width_m": 7,
        "indoor": True,
        "surface": "Wood",
        "elevation_m": 121,
        "default_temp_c": 21,
        "wall_angles": {"straight_deg": 13, "curve_deg": 42},
        "notes": None,
    }
    return {**entry, **changes}


def _write(tmp_path: Path, *entries: dict) -> Path:
    path = tmp_path / "facilities.json"
    path.write_text(json.dumps({"_readme": ["ignored"], "tracks": list(entries)}), encoding="utf-8")
    return path


def test_load_profiles_reads_the_file_layout(tmp_path):
    profile = load_profiles(_write(tmp_path, _entry()))[_ACCOUNT]
    assert profile["name"] == "Bromont - CNCB"
    assert (profile["city"], profile["latitude"], profile["longitude"]) == ("Bromont", 45.3, -72.7)
    assert (profile["length_m"], profile["width_m"], profile["indoor"], profile["surface"]) == (250, 7, True, "Wood")
    assert (profile["bank_straight_deg"], profile["bank_curve_deg"]) == (13, 42)
    assert profile["notes"] is None


def test_the_bundled_facilities_file_is_valid():
    # A bad file would stop the backend from starting; catch it in CI instead.
    profiles = load_profiles(FACILITIES_FILE)
    assert profiles
    assert all(profile["name"] for profile in profiles.values())


def test_load_profiles_treats_blank_and_null_as_unknown(tmp_path):
    profile = load_profiles(_write(tmp_path, _entry(track_name="  ", surface="", length_m=None, wall_angles=None)))[_ACCOUNT]
    assert (profile["name"], profile["surface"], profile["length_m"]) == (None, None, None)
    assert (profile["bank_straight_deg"], profile["bank_curve_deg"]) == (None, None)


@pytest.mark.parametrize(
    "entry",
    [
        _entry(sqorz_account_id=""),
        _entry(length_m="250 m"),
        _entry(length_m=0),
        _entry(indoor="yes"),
        _entry(localisation={"latitude": "45.3121° N"}),
        _entry(wall_angles={"curve_deg": 120}),
    ],
)
def test_load_profiles_rejects_bad_entries(tmp_path, entry):
    with pytest.raises(InvalidFacilityFile):
        load_profiles(_write(tmp_path, entry))


def test_load_profiles_rejects_a_repeated_account_and_a_broken_file(tmp_path):
    with pytest.raises(InvalidFacilityFile, match="twice"):
        load_profiles(_write(tmp_path, _entry(), _entry()))
    broken = tmp_path / "broken.json"
    broken.write_text("{nope")
    with pytest.raises(InvalidFacilityFile):
        load_profiles(broken)
    with pytest.raises(InvalidFacilityFile):
        load_profiles(tmp_path / "missing.json")


async def test_import_names_every_track_of_the_account(client, db_session, tmp_path):
    athlete_id = await _athlete_with_track(client, db_session)
    async with db_session() as session:
        covered = await import_profiles(session, load_profiles(_write(tmp_path, _entry())))
        await session.commit()
    assert covered == {_ACCOUNT: ["Tour complet"]}

    track = await _track_by_new_name(client, athlete_id)
    assert track["name"] == "Bromont - CNCB"
    assert track["sqorz_name"] == "Tour complet"
    assert (track["city"], track["country"], track["latitude"], track["longitude"]) == ("Bromont", "Canada", 45.3, -72.7)
    assert (track["length_m"], track["width_m"], track["indoor"], track["surface"]) == (250, 7, True, "Wood")
    assert (track["bank_straight_deg"], track["bank_curve_deg"]) == (13, 42)


async def _track_by_new_name(client, athlete_id) -> dict:
    tracks = (await client.get(f"/athletes/{athlete_id}/tracks")).json()
    return next(t for t in tracks if t["name"] == "Bromont - CNCB")


async def test_import_keeps_what_the_file_leaves_null_and_reports_unknown_accounts(client, db_session, tmp_path):
    athlete_id = await _athlete_with_track(client, db_session, admin=True)
    track = await _track(client, athlete_id)
    assert (await client.patch(f"/tracks/{track['id']}", json={"elevation_m": 99, "notes": "hand written"})).status_code == 200

    profiles = load_profiles(_write(tmp_path, _entry(elevation_m=None, notes=None), _entry(sqorz_account_id="other")))
    async with db_session() as session:
        covered = await import_profiles(session, profiles)
        await session.commit()
    assert covered["other"] == []

    updated = await _track_by_new_name(client, athlete_id)
    assert (updated["elevation_m"], updated["notes"]) == (99, "hand written")


async def test_a_resync_keeps_the_hand_set_name_and_tracks_sqorzs(client, db_session, tmp_path):
    athlete_id = await _athlete_with_track(client, db_session)
    async with db_session() as session:
        await import_profiles(session, load_profiles(_write(tmp_path, _entry())))
        await session.commit()

    payload = json.loads(_FIXTURE.read_text())
    payload["eventTrainingDetails"] = [
        e for e in payload["eventTrainingDetails"] if e["trainingDetail"]["eventDate"] == _SESSION_DATE
    ]
    for detail in payload["eventTrainingDetails"]:
        for track in detail["trainingDetail"]["tracks"]:
            track["trackName"] = "Renamed in sqorz"
    async with db_session() as session:
        await normalize_snapshot(session, payload)
        await session.commit()

    track = await _track_by_new_name(client, athlete_id)
    assert track["sqorz_name"] == "Renamed in sqorz"


async def test_a_track_sqorz_adds_later_takes_the_facilitys_profile(client, db_session, tmp_path, monkeypatch):
    await _athlete_with_track(client, db_session)
    profiles = load_profiles(_write(tmp_path, _entry()))
    monkeypatch.setattr("app.training.facility.known_profiles", lambda: profiles)

    payload = json.loads(_FIXTURE.read_text())
    payload["eventTrainingDetails"] = [
        e for e in payload["eventTrainingDetails"] if e["trainingDetail"]["eventDate"] == _SESSION_DATE
    ][:1]
    payload["eventTrainingDetails"][0]["trainingDetail"]["tracks"][0]["trackId"] = "brand-new"
    async with db_session() as session:
        await normalize_snapshot(session, payload)
        await session.commit()

    async with db_session() as session:
        added = await session.scalar(select(Track).where(Track.external_track_id == "brand-new"))
    assert added.name == "Bromont - CNCB"
    assert added.sqorz_name == "Tour complet"
    assert (added.length_m, added.surface, added.bank_curve_deg) == (250, "Wood", 42)


async def test_a_track_without_a_profile_shows_the_sqorz_name(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session)
    track = await _track(client, athlete_id)
    assert track["name"] == "Tour complet"
    assert track["sqorz_name"] is None


async def test_a_new_velodromes_tracks_are_named_on_their_first_sync(client, db_session, tmp_path, monkeypatch):
    profiles = load_profiles(_write(tmp_path, _entry()))
    monkeypatch.setattr("app.training.facility.known_profiles", lambda: profiles)
    athlete_id = await _athlete_with_track(client, db_session)

    track = await _track_by_new_name(client, athlete_id)
    assert track["sqorz_name"] == "Tour complet"
    assert (track["length_m"], track["bank_curve_deg"]) == (250, 42)
    # The length came with the track, so multi-lap records exist from the start.
    board = (await client.get(f"/athletes/{athlete_id}/records")).json()
    assert any(row["event_key"] == "500m" for row in board)

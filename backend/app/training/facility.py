"""A facility's profile — the hand-set facts about the venue (display name,
location, size, banking…), kept on each of its tracks.

Sqorz scopes tracks by `account_id` (the facility) and gives a venue several
of them ("Tour complet" twice, a gated line…), so a profile is applied to
every track of the account. The profiles live in `facilities.json` next to
this module, part of the code: the backend applies them on every start
(`python -m app.training.cli apply-facilities`, run by the Dockerfiles before
uvicorn) and the sqorz normalizer applies them to a track it creates
(`apply_known_profile`), so adding a velodrome is an edit and a deploy.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.training.models import EventTrack, Track, TrainingLap
from app.training.records_service import recompute_many

# Everything copied from a profile to a track, besides the name.
PROFILE_FIELDS = (
    "city",
    "region",
    "country",
    "latitude",
    "longitude",
    "length_m",
    "width_m",
    "indoor",
    "surface",
    "elevation_m",
    "default_temp_c",
    "bank_straight_deg",
    "bank_curve_deg",
    "notes",
)


FACILITIES_FILE = Path(__file__).with_name("facilities.json")


class InvalidFacilityFile(Exception):
    pass


@cache
def known_profiles() -> dict[str, dict[str, Any]]:
    """The profiles of `FACILITIES_FILE`, read once per process."""
    return load_profiles(FACILITIES_FILE)


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    """`sqorz_account_id` → profile (`name` + `PROFILE_FIELDS`, null = unknown).
    Entries are checked as a whole, so a typo fails before anything is
    written.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InvalidFacilityFile(f"Can't read {path}: {exc}") from exc
    entries = raw.get("tracks") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        raise InvalidFacilityFile('Expected an object with a "tracks" list')

    profiles: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries, start=1):
        where = f"tracks[{index}]"
        account_id = entry.get("sqorz_account_id") if isinstance(entry, dict) else None
        if not isinstance(account_id, str) or not account_id:
            raise InvalidFacilityFile(f"{where}: sqorz_account_id is missing")
        if account_id in profiles:
            raise InvalidFacilityFile(f"{where}: sqorz_account_id {account_id} appears twice")

        place = entry.get("localisation") or {}
        angles = entry.get("wall_angles") or {}
        profile: dict[str, Any] = {
            "name": _text(entry.get("track_name")),
            "city": _text(place.get("city")),
            "region": _text(place.get("region")),
            "country": _text(place.get("country")),
            "latitude": _number(place.get("latitude"), where, "latitude", -90, 90),
            "longitude": _number(place.get("longitude"), where, "longitude", -180, 180),
            "length_m": _number(entry.get("length_m"), where, "length_m", 1, 1000),
            "width_m": _number(entry.get("width_m"), where, "width_m", 0.1, 100),
            "indoor": _flag(entry.get("indoor"), where),
            "surface": _text(entry.get("surface")),
            "elevation_m": _number(entry.get("elevation_m"), where, "elevation_m", -500, 6000),
            "default_temp_c": _number(entry.get("default_temp_c"), where, "default_temp_c", -40, 60),
            "bank_straight_deg": _number(angles.get("straight_deg"), where, "straight_deg", 0, 90),
            "bank_curve_deg": _number(angles.get("curve_deg"), where, "curve_deg", 0, 90),
            "notes": _text(entry.get("notes")),
        }
        profiles[account_id] = profile
    return profiles


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number(value: Any, where: str, field: str, low: float, high: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise InvalidFacilityFile(f"{where}.{field}: expected a number between {low} and {high}, got {value!r}")
    return float(value)


def _flag(value: Any, where: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise InvalidFacilityFile(f"{where}.indoor: expected true, false or null, got {value!r}")


def apply_profile(track: Track, profile: dict[str, Any]) -> None:
    """Sets the profile on the track. A null leaves the track's current value:
    the file says what is known, it never erases what someone entered.
    """
    if profile.get("name"):
        track.name = profile["name"]
        track.name_is_custom = True
    for field in PROFILE_FIELDS:
        if profile.get(field) is not None:
            setattr(track, field, profile[field])


async def import_profiles(db: AsyncSession, profiles: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Applies each profile to every track of its account (the caller
    commits). Returns account id → the sqorz names of the tracks it covers; an
    account without tracks yet maps to an empty list. A changed length changes
    which records exist, so those athletes' records are recomputed, as when
    the length is edited in the track settings.
    """
    result: dict[str, list[str]] = {}
    resized: list[Track] = []
    for account_id, profile in profiles.items():
        tracks = (await db.scalars(select(Track).where(Track.sqorz_account_id == account_id))).all()
        for track in tracks:
            before = track.length_m
            apply_profile(track, profile)
            if track.length_m != before:
                resized.append(track)
        result[account_id] = [track.sqorz_name or track.name for track in tracks]
    await db.flush()
    if resized:
        athlete_ids = (
            await db.scalars(
                select(TrainingLap.athlete_id)
                .join(EventTrack, EventTrack.id == TrainingLap.event_track_id)
                .where(EventTrack.track_id.in_([track.id for track in resized]))
                .distinct()
            )
        ).all()
        await recompute_many(db, athlete_ids)
    return result


def apply_known_profile(track: Track) -> None:
    """A track sqorz has just created takes its facility's profile, if the
    file has one. (It has no laps yet, so no records to recompute.)
    """
    profile = known_profiles().get(track.sqorz_account_id)
    if profile is not None:
        apply_profile(track, profile)

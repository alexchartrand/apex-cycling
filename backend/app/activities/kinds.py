"""What kind of training an activity is.

Sources name it in their own vocabularies (FIT `sport`/`sub_sport`, TCX
`Sport`, GPX `<type>`, Intervals.icu and Strava activity types) and are often
wrong — a trainer ride arrives as plain "cycling" — so `classify` gives the
best guess and the athlete may override it (`Activity.activity_type_manual`).

Stored as a plain string column (not a database enum) so a new kind is just a
new member here. Power analysis only ever reads `CYCLING_TYPES`, so the power
of a future running activity can't leak into the cycling power curve.
"""

import enum
import re


class ActivityType(str, enum.Enum):
    CYCLING = "cycling"
    TRACK_CYCLING = "track_cycling"
    INDOOR_CYCLING = "indoor_cycling"
    STRENGTH = "strength"
    OTHER = "other"


CYCLING_TYPES: frozenset[ActivityType] = frozenset(
    {ActivityType.CYCLING, ActivityType.TRACK_CYCLING, ActivityType.INDOOR_CYCLING}
)
CYCLING_TYPE_VALUES: tuple[str, ...] = tuple(sorted(t.value for t in CYCLING_TYPES))

# The sports an athlete says they do (`Athlete.sports`): what the app shows them.
# Coarser than activity types — indoor rides are "cycling". Running joins here.
ATHLETE_SPORTS: tuple[str, ...] = (ActivityType.TRACK_CYCLING.value, ActivityType.CYCLING.value, ActivityType.STRENGTH.value)

# The sports a training plan can be for (`training_plans`).
PLAN_SPORTS: tuple[str, ...] = (ActivityType.CYCLING.value, ActivityType.TRACK_CYCLING.value)

# Normalized (lower case, letters only) source names → kind.
_NAMES: dict[str, ActivityType] = {
    # FIT sport / sub_sport (fitdecode's names), TCX, GPX
    "cycling": ActivityType.CYCLING,
    "biking": ActivityType.CYCLING,
    "bike": ActivityType.CYCLING,
    "road": ActivityType.CYCLING,
    "mountain": ActivityType.CYCLING,
    "gravelcycling": ActivityType.CYCLING,
    "cyclocross": ActivityType.CYCLING,
    "ebiking": ActivityType.CYCLING,
    "trackcycling": ActivityType.TRACK_CYCLING,
    "indoorcycling": ActivityType.INDOOR_CYCLING,
    "virtualactivity": ActivityType.INDOOR_CYCLING,
    "spin": ActivityType.INDOOR_CYCLING,
    "training": ActivityType.STRENGTH,
    "strengthtraining": ActivityType.STRENGTH,
    "fitnessequipment": ActivityType.STRENGTH,
    # Intervals.icu / Strava activity types
    "ride": ActivityType.CYCLING,
    "gravelride": ActivityType.CYCLING,
    "mountainbikeride": ActivityType.CYCLING,
    "ebikeride": ActivityType.CYCLING,
    "emountainbikeride": ActivityType.CYCLING,
    "velomobile": ActivityType.CYCLING,
    "handcycle": ActivityType.CYCLING,
    "trackride": ActivityType.TRACK_CYCLING,
    "virtualride": ActivityType.INDOOR_CYCLING,
    "weighttraining": ActivityType.STRENGTH,
    "crossfit": ActivityType.STRENGTH,
    "workout": ActivityType.STRENGTH,
}

# A specific answer beats a vague one: "cycling" + "indoor_cycling" is indoor.
_SPECIFICITY = {
    ActivityType.OTHER: 0,
    ActivityType.CYCLING: 1,
    ActivityType.STRENGTH: 2,
    ActivityType.TRACK_CYCLING: 3,
    ActivityType.INDOOR_CYCLING: 3,
}


def detected_type(activity) -> ActivityType:
    """What the activity is when the athlete hasn't said: track cycling when
    it is linked to a sqorz session (those are velodrome laps), else the
    source's sport."""
    if activity.training_event_id is not None:
        return ActivityType.TRACK_CYCLING
    return classify(activity.sport)


def refresh_type(activity) -> None:
    """Re-derives the type unless the athlete chose it."""
    if not activity.activity_type_manual:
        activity.activity_type = detected_type(activity).value


def _kind_of(name: str | None) -> ActivityType | None:
    if not name:
        return None
    key = re.sub(r"[^a-z]", "", name.lower())
    if key in ("generic", "all", "invalid", ""):
        return None
    return _NAMES.get(key, ActivityType.OTHER)


def source_sport(*names: str | None) -> str | None:
    """The source's names for the sport (FIT sport and sub-sport, the
    platform's type…) as the one raw `Activity.sport` string, "cycling/indoor_cycling",
    so `classify` can be re-run from the stored row alone."""
    seen: list[str] = []
    for name in names:
        name = (name or "").strip()
        if name and name.lower() not in ("generic", "none") and name.lower() not in (s.lower() for s in seen):
            seen.append(name)
    return "/".join(seen)[:64] or None


def classify(*names: str | None) -> ActivityType:
    """The most specific kind any of the source's names gives (sport,
    sub-sport, the platform's own type…, each possibly "a/b" as `source_sport`
    joins them); cycling when none is stated, since that is what this app is for."""
    parts = [part for name in names if name for part in name.split("/")]
    kinds = [kind for kind in map(_kind_of, parts) if kind is not None]
    if not kinds:
        return ActivityType.CYCLING
    return max(kinds, key=lambda kind: _SPECIFICITY[kind])

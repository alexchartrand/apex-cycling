"""What a step tells the rider, as one line of text: label, event and start,
laps, target time, gear, RPE and notes ("Flying – flying 200 (flying
start) – 11.200 s – 50×15"). The Intervals.icu text, the FIT step notes,
Zwift's text events and the ERG/MRC course text all show it. Pure.
"""

from app.notifications.messages import DEFAULT_LOCALE, event_name, format_time
from app.workouts.schemas import WorkoutStep

_WORDS = {
    "en": {"standing": "standing start", "flying": "flying start", "laps": "{n} laps", "lap": "1 lap"},
    "fr": {"standing": "départ arrêté", "flying": "départ lancé", "laps": "{n} tours", "lap": "1 tour"},
}


def language(locale: str | None) -> str:
    """A saved locale ("fr-CA", None…) as one of the languages cues are written in."""
    return locale[:2] if locale and locale[:2] in _WORDS else DEFAULT_LOCALE


def step_name(step: WorkoutStep, locale: str = DEFAULT_LOCALE) -> str | None:
    """A short title: the label, else the event."""
    if step.label:
        return step.label
    return event_name(step.event_key, locale) if step.event_key else None


def step_cue(step: WorkoutStep, locale: str = DEFAULT_LOCALE) -> str:
    words = _WORDS.get(locale, _WORDS[DEFAULT_LOCALE])
    parts: list[str] = []
    if step.label:
        parts.append(step.label)
    if step.event_key:
        event = event_name(step.event_key, locale)
        if step.start_type is not None and step.start_type.value in words:
            event = f"{event} ({words[step.start_type.value]})"
        parts.append(event)
    if step.laps is not None and step.duration_s is None:
        parts.append(words["lap"] if step.laps == 1 else words["laps"].format(n=step.laps))
    if step.target_time_ms is not None:
        parts.append(format_time(step.target_time_ms))
    if step.gear is not None:
        parts.append(f"{step.gear.chainring_teeth}×{step.gear.cog_teeth}")
    if step.rpe is not None:
        parts.append(f"RPE {step.rpe}")
    if step.notes:
        parts.append(step.notes)
    return " ".join(" – ".join(parts).split())

"""A planned workout as an Intervals.icu calendar event, its steps written in
Intervals.icu's native workout text (the `description` field; checked
against the forum's "Workout builder syntax quick guide", 2026-10):

    3x
    - Flying 200 – 11.200 s – 50×15 20s 150% press lap intensity=interval
    - 3m 50% 90rpm intensity=recovery

Whatever precedes a step's length is its cue text, so the cue goes first and
anything in it that the parser could take for a length or a target ("15s",
"3x", "Z2") is spaced out. `m` means minutes there; metres are `mtr`.
Intervals.icu has no nested repeats, so an outer repeat that holds one is
unrolled. Track steps (laps, an event) end on the lap button, with an
estimated duration so Intervals.icu can draw and score them. Power stays
as written (% of FTP or watts): Intervals.icu applies the athlete's FTP.
Pure.
"""

import re
from collections.abc import Sequence
from datetime import date

from app.notifications.messages import DEFAULT_LOCALE
from app.workouts import structure
from app.workouts.cues import language, step_cue
from app.workouts.schemas import InnerRepeat, RepeatBlock, StepKind, WorkoutStep
from app.workouts.structure import OPEN_STEP_S

_INTENSITY = {
    StepKind.WARMUP: "warmup",
    StepKind.WORK: "interval",
    StepKind.RECOVERY: "recovery",
    StepKind.COOLDOWN: "cooldown",
}

# A number glued to something the parser reads as a unit, and zone names.
_NUMBER_UNIT = re.compile(r"(\d)(?=(?:h|m|s|min|sec|km|mtr|mi|w|rpm|x|%|'|\")(?![a-z]))", re.IGNORECASE)
_ZONE = re.compile(r"\b([zZ])(\d)")
_REPEAT_END = re.compile(r"\d\s*x$", re.IGNORECASE)


def _defuse(text: str) -> str:
    """Free text that the workout parser won't read as steps or targets."""
    text = " ".join(text.split())
    return _ZONE.sub(r"\1 \2", _NUMBER_UNIT.sub(r"\1 ", text))


def _number(value: float) -> str:
    return f"{value:g}"


def format_duration(seconds: float) -> str:
    """1h2m30s, 5m, 45s."""
    total = max(1, round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return "".join(f"{v}{unit}" for v, unit in ((hours, "h"), (minutes, "m"), (secs, "s")) if v) or "1s"


def format_distance(metres: float) -> str:
    return f"{round(metres / 1000)}km" if metres >= 1000 and metres % 1000 == 0 else f"{round(metres)}mtr"


def step_line(step: WorkoutStep, locale: str = DEFAULT_LOCALE) -> str:
    tokens = ["-"]
    if cue := _defuse(step_cue(step, locale)):
        tokens.append(cue)
    press_lap = False
    if step.duration_s is not None:
        tokens.append(format_duration(step.duration_s))
    elif step.is_track:
        tokens.append(format_duration(structure.step_duration_s(step, structure.DEFAULT_TRACK_LENGTH_M) or OPEN_STEP_S))
        press_lap = True
    elif step.distance_m is not None:
        tokens.append(format_distance(step.distance_m))
    else:
        tokens.append(format_duration(OPEN_STEP_S))
        press_lap = True
    if step.power is not None:
        unit = "%" if step.power.unit == "ftp_pct" else "w"
        span = _number(step.power.low) if step.power.high is None else f"{_number(step.power.low)}-{_number(step.power.high)}"
        tokens.append(span + unit)
    if step.cadence is not None:
        high = f"-{step.cadence.high}" if step.cadence.high is not None else ""
        tokens.append(f"{step.cadence.low}{high}rpm")
    if press_lap:
        tokens.append("press lap")
    tokens.append(f"intensity={_INTENSITY[step.kind]}")
    return " ".join(tokens)


def workout_text(items: Sequence[WorkoutStep | RepeatBlock], locale: str = DEFAULT_LOCALE) -> str:
    """The steps in blocks separated by an empty line, each repeat its own
    block headed "Nx" (the syntax wants the empty lines around repeats)."""
    blocks: list[list[str]] = []
    plain: list[str] = []

    def flush() -> None:
        if plain:
            blocks.append(plain.copy())
            plain.clear()

    def emit(entries: Sequence[WorkoutStep | RepeatBlock | InnerRepeat]) -> None:
        for item in entries:
            if isinstance(item, WorkoutStep):
                plain.append(step_line(item, locale))
            elif all(isinstance(inner, WorkoutStep) for inner in item.steps):
                flush()
                blocks.append([f"{item.count}x", *(step_line(s, locale) for s in item.steps)])
            else:
                for _ in range(item.count):  # nested: unroll the outer repeat
                    emit(item.steps)

    emit(items)
    flush()
    return "\n\n".join("\n".join(block) for block in blocks)


def _free_text(text: str) -> str:
    """The plan's own description, kept from being read as steps: a line
    starting with a dash or ending in "Nx" would be one."""
    lines = []
    for line in text.splitlines():
        line = line.rstrip()
        if line.lstrip().startswith("-"):
            line = "• " + line.lstrip().lstrip("-").lstrip()
        if _REPEAT_END.search(line):
            line += "."
        lines.append(line)
    return "\n".join(lines).strip()


def event_uid(plan_id) -> str:
    """Our mark on the event: creating with it twice updates instead of duplicating."""
    return f"apex-cycling-plan-{plan_id}"


def event_payload(
    *,
    plan_id,
    title: str,
    planned_date: date,
    description: str | None,
    items: Sequence[WorkoutStep | RepeatBlock],
    locale: str | None,
) -> dict:
    text = workout_text(items, language(locale))
    if description and description.strip():
        text = f"{_free_text(description)}\n\n{text}"
    return {
        "category": "WORKOUT",
        "type": "Ride",
        "start_date_local": f"{planned_date.isoformat()}T00:00:00",
        "name": title,
        "description": text,
        "uid": event_uid(plan_id),
    }

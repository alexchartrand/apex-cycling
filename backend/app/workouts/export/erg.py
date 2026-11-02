"""`.erg` (watts) and `.mrc` (% of FTP) course files, the plain-text format
TrainerRoad, Golden Cheetah, PerfPRO and most ERG apps read: two points per
step (the same value twice, or a ramp), and each step's cue in the course
text. Every step needs a number, so a step without a target goes at
`fallback_fraction`. Raises `NeedsFtp` when a target has to change unit and
the FTP isn't known. Pure.
"""

from collections.abc import Sequence
from typing import Literal

from app.workouts.export.common import ExportContext, NeedsFtp, TrainerStep, fallback_fraction, one_line, trainer_steps
from app.workouts.schemas import InnerRepeat, RepeatBlock, StepKind, WorkoutStep

# How long a cue stays on screen.
TEXT_S = 10


def _points(trainer: TrainerStep, unit: Literal["watts", "percent"], ftp_w: float | None) -> tuple[float, float]:
    """The values at the start and the end of the step."""
    step = trainer.step
    if step.power is not None and step.power.unit == ("watts" if unit == "watts" else "ftp_pct"):
        low, high = step.power.low, step.power.high if step.power.high is not None else step.power.low
    elif unit == "percent" and step.power is None:
        low = high = fallback_fraction(step) * 100
    else:
        if ftp_w is None:
            raise NeedsFtp
        fractions = trainer.power or (fallback_fraction(step),) * 2
        scale = ftp_w if unit == "watts" else 100
        low, high = fractions[0] * scale, fractions[1] * scale
    if not trainer.is_ramp:
        return (low + high) / 2, (low + high) / 2
    return (low, high) if step.kind == StepKind.WARMUP else (high, low)


def write_course(
    *,
    unit: Literal["watts", "percent"],
    name: str,
    description: str | None,
    items: Sequence[WorkoutStep | RepeatBlock | InnerRepeat],
    context: ExportContext,
) -> bytes:
    """`unit` "watts" writes an `.erg`, "percent" an `.mrc`."""
    trainers = trainer_steps(items, context)
    header = ["[COURSE HEADER]", "VERSION = 2", "UNITS = ENGLISH", f"DESCRIPTION = {one_line(description)}"]
    header.append(f"FILE NAME = {one_line(name)}")
    if unit == "watts" and context.ftp_w:
        header.append(f"FTP = {round(context.ftp_w)}")
    header += [f"MINUTES {'WATTS' if unit == 'watts' else 'PERCENT'}", "[END COURSE HEADER]"]

    data = ["[COURSE DATA]"]
    text = ["[COURSE TEXT]"]
    for trainer in trainers:
        start, end = _points(trainer, unit, context.ftp_w)
        begin, finish = trainer.start_s / 60, (trainer.start_s + trainer.duration_s) / 60
        data += [f"{begin:.2f}\t{start:.0f}", f"{finish:.2f}\t{end:.0f}"]
        if trainer.cue:
            text.append(f"{round(trainer.start_s)}\t{one_line(trainer.cue)}\t{min(TEXT_S, round(trainer.duration_s))}")
    data.append("[END COURSE DATA]")
    text.append("[END COURSE TEXT]")
    lines = header + data + (text if len(text) > 2 else [])
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")

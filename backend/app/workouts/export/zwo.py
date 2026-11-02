"""A Zwift workout (`.zwo`). Power stays in fractions of FTP, since Zwift
applies the rider's own; a step without a target (or with one in watts and
no known FTP) is a free ride, which is also how a track effort comes out.
Each step shows its cue as a text event. Pure.
"""

from collections.abc import Sequence
from xml.etree import ElementTree as ET

from app.workouts.export.common import ExportContext, TrainerStep, one_line, trainer_steps
from app.workouts.schemas import InnerRepeat, RepeatBlock, StepKind, WorkoutStep


def _fraction(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _element(parent: ET.Element, trainer: TrainerStep) -> None:
    attributes = {"Duration": str(round(trainer.duration_s))}
    if trainer.power is None:
        tag = "FreeRide"
        attributes["FlatRoad"] = "1"
    elif trainer.is_ramp:
        low, high = trainer.power
        tag = "Warmup" if trainer.step.kind == StepKind.WARMUP else "Cooldown"
        # A cooldown runs from PowerLow down to PowerHigh.
        start, end = (low, high) if tag == "Warmup" else (high, low)
        attributes |= {"PowerLow": _fraction(start), "PowerHigh": _fraction(end)}
    else:
        tag = "SteadyState"
        attributes["Power"] = _fraction(sum(trainer.power) / 2)
    if (cadence := trainer.step.cadence) is not None:
        attributes["Cadence"] = str(cadence.low if cadence.high is None else round((cadence.low + cadence.high) / 2))
    element = ET.SubElement(parent, tag, attributes)
    if trainer.cue:
        ET.SubElement(element, "textevent", {"timeoffset": "0", "message": trainer.cue})


def write_zwo(
    *,
    name: str,
    description: str | None,
    tags: Sequence[str],
    items: Sequence[WorkoutStep | RepeatBlock | InnerRepeat],
    context: ExportContext,
) -> bytes:
    root = ET.Element("workout_file")
    ET.SubElement(root, "author").text = "ApexCycling"
    ET.SubElement(root, "name").text = one_line(name)
    ET.SubElement(root, "description").text = description or ""
    ET.SubElement(root, "sportType").text = "bike"
    tag_list = ET.SubElement(root, "tags")
    for tag in tags:
        ET.SubElement(tag_list, "tag", {"name": tag})
    workout = ET.SubElement(root, "workout")
    for trainer in trainer_steps(items, context):
        _element(workout, trainer)
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=False) + b"\n"

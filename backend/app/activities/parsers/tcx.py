from datetime import datetime

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.activities.parsers.base import ActivityParseError, ParsedActivity, Sample, build_activity


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _float(element) -> float | None:
    try:
        return float(element.text)
    except (TypeError, ValueError):
        return None


def _point(trackpoint) -> Sample | None:
    values: dict[str, float | None] = {}
    moment = None
    for child in trackpoint:
        name = _local(child.tag)
        if name == "Time":
            try:
                moment = datetime.fromisoformat(child.text.strip())
            except (AttributeError, ValueError):
                return None
        elif name in ("AltitudeMeters", "DistanceMeters", "Cadence"):
            values[name] = _float(child)
        elif name == "HeartRateBpm":
            values["hr"] = next((_float(v) for v in child if _local(v.tag) == "Value"), None)
        elif name == "Extensions":
            # Garmin's activity extension (TPX): Speed in m/s, Watts.
            for extension in child.iter():
                if _local(extension.tag) == "Speed":
                    values["speed"] = _float(extension)
                elif _local(extension.tag) == "Watts":
                    values["watts"] = _float(extension)
    if moment is None:
        return None
    return Sample(
        time=moment,
        power_w=values.get("watts"),
        heart_rate=values.get("hr"),
        cadence=values.get("Cadence"),
        speed_mps=values.get("speed"),
        distance_m=values.get("DistanceMeters"),
        altitude_m=values.get("AltitudeMeters"),
    )


def parse(content: bytes) -> ParsedActivity:
    try:
        root = ElementTree.fromstring(content)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise ActivityParseError(f"invalid TCX file: {exc}") from exc

    sport = None
    timer_s = 0.0
    samples: list[Sample] = []
    for element in root.iter():
        name = _local(element.tag)
        if name == "Activity":
            sport = sport or element.get("Sport")
        elif name == "Lap":
            lap_time = next((_float(c) for c in element if _local(c.tag) == "TotalTimeSeconds"), None)
            timer_s += lap_time or 0.0
        elif name == "Trackpoint":
            point = _point(element)
            if point is not None:
                samples.append(point)
    return build_activity(samples, sport=sport, timer_s=timer_s or None)

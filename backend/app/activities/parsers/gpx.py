from datetime import datetime

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.activities.parsers.base import ActivityParseError, ParsedActivity, Sample, build_activity


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _float(text: str | None) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _point(trackpoint) -> Sample | None:
    latitude, longitude = _float(trackpoint.get("lat")), _float(trackpoint.get("lon"))
    values: dict[str, float | None] = {}
    moment = None
    for child in trackpoint.iter():
        name = _local(child.tag)
        if name == "time":
            try:
                moment = datetime.fromisoformat(child.text.strip())
            except (AttributeError, ValueError):
                return None
        elif name in ("ele", "hr", "cad", "speed", "power", "PowerInWatts"):
            # Garmin's TrackPointExtension (hr, cad), the common <power> tag
            # and the PowerExtension (PowerInWatts) all end up here.
            values[name] = _float(child.text)
    if moment is None:
        return None
    return Sample(
        time=moment,
        power_w=values.get("power", values.get("PowerInWatts")),
        heart_rate=values.get("hr"),
        cadence=values.get("cad"),
        speed_mps=values.get("speed"),
        altitude_m=values.get("ele"),
        latitude=latitude,
        longitude=longitude,
    )


def parse(content: bytes) -> ParsedActivity:
    try:
        root = ElementTree.fromstring(content)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise ActivityParseError(f"invalid GPX file: {exc}") from exc

    name = None
    sport = None
    samples: list[Sample] = []
    for element in root.iter():
        tag = _local(element.tag)
        if tag == "trk":
            name = name or next((c.text for c in element if _local(c.tag) == "name"), None)
            sport = sport or next((c.text for c in element if _local(c.tag) == "type"), None)
        elif tag == "trkpt":
            point = _point(element)
            if point is not None:
                samples.append(point)
    return build_activity(samples, sport=sport, name=name.strip() if name else None)

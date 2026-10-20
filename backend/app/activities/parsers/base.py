import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Bounds on what a sensor can plausibly report; anything outside is a glitch
# (a power meter spiking to 65535 W, a strap reading 0 bpm) and becomes "no reading".
_PLAUSIBLE = {
    "power_w": (0, 3000),
    "heart_rate": (20, 250),
    "cadence": (0, 250),
    "speed_mps": (0, 40),
}

# A day and a half of 1 Hz recording. Stops a crafted file from allocating
# arrays without bound; no real ride comes close.
MAX_SAMPLES = 130_000


class ActivityParseError(ValueError):
    """The file isn't a usable activity (corrupt, empty, wrong format)."""


@dataclass
class Sample:
    time: datetime
    power_w: float | None = None
    heart_rate: float | None = None
    cadence: float | None = None
    speed_mps: float | None = None
    distance_m: float | None = None
    altitude_m: float | None = None
    # GPX has no distance field: the parser keeps the position to derive it.
    latitude: float | None = None
    longitude: float | None = None


@dataclass
class ParsedActivity:
    """A recording in the shape every source (file or API) is reduced to.

    `time_s` is seconds since `start_time`, strictly increasing; every other
    channel is either absent (the file doesn't carry it) or a list as long as
    `time_s` with `None` where there was no reading.
    """

    start_time: datetime
    time_s: list[float]
    channels: dict[str, list[float | None]]
    sport: str | None = None
    name: str | None = None
    # The device's own timer (excludes pauses) when the file states one.
    timer_s: float | None = None
    extra: dict = field(default_factory=dict)

    @property
    def elapsed_s(self) -> float:
        return self.time_s[-1]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def build_activity(
    samples: list[Sample], *, sport: str | None = None, name: str | None = None, timer_s: float | None = None
) -> ParsedActivity:
    """Turns raw per-point samples into a `ParsedActivity`: orders them in
    time, drops repeated timestamps, blanks implausible readings, and fills in
    distance (from positions) and speed (from distance) when the file lacks
    them."""
    if len(samples) > MAX_SAMPLES:
        raise ActivityParseError(f"too many samples ({len(samples)})")
    timed = sorted(samples, key=lambda s: _as_utc(s.time))
    unique: list[Sample] = []
    for sample in timed:
        if not unique or _as_utc(sample.time) > _as_utc(unique[-1].time):
            unique.append(sample)
    if len(unique) < 2:
        raise ActivityParseError("the file has fewer than two timestamped points")

    start = _as_utc(unique[0].time)
    time_s = [(_as_utc(s.time) - start).total_seconds() for s in unique]

    for sample in unique:
        for channel, (low, high) in _PLAUSIBLE.items():
            value = getattr(sample, channel)
            if value is not None and not low <= value <= high:
                setattr(sample, channel, None)

    if not any(s.distance_m is not None for s in unique) and any(s.latitude is not None for s in unique):
        _distance_from_positions(unique)
    if not any(s.speed_mps is not None for s in unique) and any(s.distance_m is not None for s in unique):
        _speed_from_distance(unique, time_s)

    channels: dict[str, list[float | None]] = {}
    for channel in ("power_w", "heart_rate", "cadence", "speed_mps", "distance_m", "altitude_m"):
        values = [getattr(s, channel) for s in unique]
        if any(v is not None for v in values):
            channels[channel] = values
    return ParsedActivity(start_time=start, time_s=time_s, channels=channels, sport=sport, name=name, timer_s=timer_s)


def _distance_from_positions(samples: list[Sample]) -> None:
    total = 0.0
    previous: Sample | None = None
    for sample in samples:
        if sample.latitude is not None and sample.longitude is not None:
            if previous is not None:
                total += _haversine_m(previous.latitude, previous.longitude, sample.latitude, sample.longitude)
            previous = sample
        sample.distance_m = total


def _speed_from_distance(samples: list[Sample], time_s: list[float]) -> None:
    for i in range(1, len(samples)):
        before, after = samples[i - 1].distance_m, samples[i].distance_m
        if before is not None and after is not None:
            speed = (after - before) / (time_s[i] - time_s[i - 1])
            samples[i].speed_mps = speed if speed >= 0 else None


def detect_format(content: bytes) -> str | None:
    if content[8:12] == b".FIT":
        return "fit"
    head = content[:4096].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if b"<trainingcenterdatabase" in head:
        return "tcx"
    if b"<gpx" in head:
        return "gpx"
    return None


def parse_activity_file(content: bytes) -> ParsedActivity:
    """Detects the format from the content (not the file name) and parses it."""
    from app.activities.parsers import fit, gpx, tcx

    file_format = detect_format(content)
    parser = {"fit": fit.parse, "tcx": tcx.parse, "gpx": gpx.parse}.get(file_format)
    if parser is None:
        raise ActivityParseError("unsupported file: expected a FIT, TCX or GPX activity")
    parsed = parser(content)
    parsed.extra["format"] = file_format
    return parsed

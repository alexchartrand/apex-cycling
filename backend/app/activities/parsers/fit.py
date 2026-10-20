import io
from datetime import datetime

import fitdecode

from app.activities.parsers.base import ActivityParseError, Sample, build_activity, ParsedActivity


def _number(message: fitdecode.FitDataMessage, *names: str) -> float | None:
    for name in names:
        if message.has_field(name):
            value = message.get_value(name, fallback=None)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def parse(content: bytes) -> ParsedActivity:
    samples: list[Sample] = []
    sport: str | None = None
    timer_s: float | None = None
    try:
        with fitdecode.FitReader(
            io.BytesIO(content), check_crc=fitdecode.CrcCheck.RAISE, error_handling=fitdecode.ErrorHandling.RAISE
        ) as reader:
            for frame in reader:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                if frame.name == "record":
                    moment = frame.get_value("timestamp", fallback=None)
                    if not isinstance(moment, datetime):
                        continue
                    samples.append(
                        Sample(
                            time=moment,
                            power_w=_number(frame, "power"),
                            heart_rate=_number(frame, "heart_rate"),
                            cadence=_number(frame, "cadence"),
                            speed_mps=_number(frame, "enhanced_speed", "speed"),
                            distance_m=_number(frame, "distance"),
                            altitude_m=_number(frame, "enhanced_altitude", "altitude"),
                        )
                    )
                elif frame.name == "session":
                    sport = sport or frame.get_value("sport", fallback=None)
                    timer = _number(frame, "total_timer_time")
                    if timer is not None:
                        timer_s = (timer_s or 0.0) + timer
    except fitdecode.FitError as exc:
        raise ActivityParseError(f"corrupt FIT file: {exc}") from exc
    return build_activity(samples, sport=str(sport) if sport else None, timer_s=timer_s)

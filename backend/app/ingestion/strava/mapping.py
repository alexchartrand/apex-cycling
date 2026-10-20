"""Strava stream data into the shared `ParsedActivity` — pure."""

from datetime import timedelta

from app.activities.parsers.base import ActivityParseError, ParsedActivity, Sample, build_activity
from app.ingestion.strava.dtos import RemoteStravaActivity

# The stream keys the sync asks Strava for.
STREAM_KEYS = ("time", "distance", "altitude", "velocity_smooth", "heartrate", "cadence", "watts")


def to_parsed_activity(activity: RemoteStravaActivity, streams: dict[str, list]) -> ParsedActivity:
    """Samples are `start + time[i]` with whatever other streams exist.
    Strava invents a power estimate for rides without a power meter; that is
    not a measurement, so `watts` is dropped unless a meter recorded it."""
    times = streams.get("time")
    if not times:
        raise ActivityParseError("Strava returned no time stream")
    count = len(times)

    def channel(key: str) -> list | None:
        values = streams.get(key)
        return values if values and len(values) >= count else None

    watts = channel("watts") if activity.device_watts else None
    heart_rate, cadence = channel("heartrate"), channel("cadence")
    speed, distance, altitude = channel("velocity_smooth"), channel("distance"), channel("altitude")
    samples = [
        Sample(
            time=activity.start + timedelta(seconds=times[i]),
            power_w=watts[i] if watts else None,
            heart_rate=heart_rate[i] if heart_rate else None,
            cadence=cadence[i] if cadence else None,
            speed_mps=speed[i] if speed else None,
            distance_m=distance[i] if distance else None,
            altitude_m=altitude[i] if altitude else None,
        )
        for i in range(count)
    ]
    return build_activity(samples, sport=activity.sport_type, name=activity.name, timer_s=activity.moving_s)

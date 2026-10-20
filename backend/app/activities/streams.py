"""Compact storage for per-second activity channels.

A channel is a list of numbers with `None` for "no reading" (a dropped power
meter), stored as zlib-compressed little-endian float arrays, with NaN
standing in for `None`. A 3-hour ride is ~10k samples per channel, a few KB
compressed, so `activity_streams` holds one row per activity instead of one
row per sample.
"""

import math
import sys
import zlib
from array import array
from collections.abc import Sequence

# Time and distance run long enough that float32 would lose whole seconds /
# decimetres; the rest are small numbers where float32 is plenty.
_TYPECODE_BY_CHANNEL = {
    "time_s": "d",
    "distance_m": "d",
    "power_w": "f",
    "heart_rate": "f",
    "cadence": "f",
    "speed_mps": "f",
    "altitude_m": "f",
}
CHANNELS = tuple(_TYPECODE_BY_CHANNEL)


def pack(channel: str, values: Sequence[float | None]) -> bytes:
    samples = array(_TYPECODE_BY_CHANNEL[channel], (math.nan if v is None else v for v in values))
    if sys.byteorder == "big":
        samples.byteswap()
    return zlib.compress(samples.tobytes())


def unpack(channel: str, blob: bytes) -> list[float | None]:
    samples = array(_TYPECODE_BY_CHANNEL[channel])
    samples.frombytes(zlib.decompress(blob))
    if sys.byteorder == "big":
        samples.byteswap()
    return [None if math.isnan(v) else v for v in samples]

"""A FIT workout file (`file_id.type` = workout), for Garmin, Wahoo, Hammerhead
and anything else that loads `.fit` workouts. Pure.

The step tree is kept: a repeat is a `repeat_until_steps_cmplt` step after
its steps, pointing back at the first one (nested repeats too, which FIT
allows). A timed step lasts its time and a road distance its distance, but
a track step (laps, an event) and an open step end on the lap button: a
head unit's distance on a velodrome is the wheel sensor's guess, while the
rider knows where the line is. The step's cue goes in its notes.

Power is written in watts when the FTP is known (FIT custom values above
1000 are watts + 1000) and else as % of FTP, which the device applies; a
single value becomes a ±`SINGLE_TARGET_SPREAD` range, since a head unit
alerts outside a range. Cadence is the secondary target when there is a
power one, otherwise the primary.
"""

import struct
import zlib
from collections.abc import Sequence
from datetime import datetime, timezone

from app.workouts.cues import step_cue, step_name
from app.workouts.export.common import ExportContext
from app.workouts.schemas import InnerRepeat, RepeatBlock, StepKind, WorkoutStep

FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)
PROFILE_VERSION = 2141  # 21.41: has the secondary targets
_CRC_TABLE = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
              0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]  # fmt: skip

SINGLE_TARGET_SPREAD = 0.05
SINGLE_CADENCE_SPREAD_RPM = 5
MAX_NAME_BYTES = 50
MAX_TEXT_BYTES = 255  # a FIT field is at most 255 bytes, terminator included

# base type id, struct format
_ENUM = (0x00, "B")
_UINT16 = (0x84, "H")
_UINT32 = (0x86, "I")
_UINT32Z = (0x8C, "I")
_STRING = (0x07, None)

_FILE_ID, _WORKOUT, _WORKOUT_STEP = 0, 26, 27
_FILE_WORKOUT = 5
_MANUFACTURER_DEVELOPMENT = 255
_SPORT_CYCLING = 2

# wkt_step_duration, wkt_step_target, intensity
_DURATION_TIME, _DURATION_DISTANCE, _DURATION_OPEN, _DURATION_REPEAT = 0, 1, 5, 6
_TARGET_OPEN, _TARGET_CADENCE, _TARGET_POWER = 2, 3, 4
_INTENSITY = {StepKind.WORK: 0, StepKind.WARMUP: 2, StepKind.COOLDOWN: 3, StepKind.RECOVERY: 4}

Field = tuple[int, tuple[int, str | None], int | str]


def crc16(data: bytes, crc: int = 0) -> int:
    for byte in data:
        for nibble in (byte & 0xF, byte >> 4):
            crc = ((crc >> 4) & 0x0FFF) ^ _CRC_TABLE[crc & 0xF] ^ _CRC_TABLE[nibble]
    return crc


def _text(value: str, max_bytes: int) -> bytes:
    """UTF-8, cut on a character boundary, null-terminated."""
    raw = value.encode("utf-8")[: max_bytes - 1]
    return raw.decode("utf-8", errors="ignore").encode("utf-8") + b"\0"


def _message(number: int, fields: list[Field]) -> bytes:
    """A definition (local type 0) and its one data message: field sizes
    vary with the strings, so every message carries its own definition."""
    definition = bytes([0x40, 0, 0]) + struct.pack("<HB", number, len(fields))
    data = b"\0"
    for field_number, (base_type, code), value in fields:
        raw = value if code is None else struct.pack("<" + code, value)
        definition += bytes([field_number, len(raw), base_type])
        data += raw
    return definition + data


def _range(low: float, high: float | None, spread: float) -> tuple[float, float]:
    if high is not None:
        return low, high
    return low - spread, low + spread


def _power_values(step: WorkoutStep, ftp_w: float | None) -> tuple[int, int]:
    power = step.power
    low, high = power.low, power.high if power.high is not None else power.low
    if power.unit == "ftp_pct" and ftp_w:
        low, high = low / 100 * ftp_w, high / 100 * ftp_w
    if power.high is None:
        low, high = low * (1 - SINGLE_TARGET_SPREAD), high * (1 + SINGLE_TARGET_SPREAD)
    offset = 0 if power.unit == "ftp_pct" and not ftp_w else 1000
    return round(low) + offset, round(high) + offset


def _cadence_values(step: WorkoutStep) -> tuple[int, int]:
    low, high = _range(step.cadence.low, step.cadence.high, SINGLE_CADENCE_SPREAD_RPM)
    return round(low), round(high)


def _step_fields(index: int, step: WorkoutStep, context: ExportContext) -> list[Field]:
    fields: list[Field] = [(254, _UINT16, index)]
    name = step_name(step, context.locale)
    if name:
        fields.append((0, _STRING, _text(name, MAX_NAME_BYTES)))
    if step.duration_s is not None:
        fields += [(1, _ENUM, _DURATION_TIME), (2, _UINT32, step.duration_s * 1000)]
    elif step.distance_m is not None and not step.is_track:
        fields += [(1, _ENUM, _DURATION_DISTANCE), (2, _UINT32, round(step.distance_m * 100))]
    else:
        fields.append((1, _ENUM, _DURATION_OPEN))
    targets: list[tuple[int, tuple[int, int]]] = []
    if step.power is not None:
        targets.append((_TARGET_POWER, _power_values(step, context.ftp_w)))
    if step.cadence is not None:
        targets.append((_TARGET_CADENCE, _cadence_values(step)))
    if not targets:
        fields.append((3, _ENUM, _TARGET_OPEN))
    for (kind, (low, high)), numbers in zip(targets, ((3, 4, 5, 6), (19, 20, 21, 22))):
        fields += [(numbers[0], _ENUM, kind), (numbers[1], _UINT32, 0), (numbers[2], _UINT32, low), (numbers[3], _UINT32, high)]
    fields.append((7, _ENUM, _INTENSITY[step.kind]))
    if (cue := step_cue(step, context.locale)) and cue != name:
        fields.append((8, _STRING, _text(cue, MAX_TEXT_BYTES)))
    return fields


def _steps(items: Sequence[WorkoutStep | RepeatBlock | InnerRepeat], context: ExportContext) -> list[list[Field]]:
    steps: list[list[Field]] = []

    def emit(entries: Sequence[WorkoutStep | RepeatBlock | InnerRepeat]) -> None:
        for item in entries:
            if isinstance(item, WorkoutStep):
                steps.append(_step_fields(len(steps), item, context))
            else:
                first = len(steps)
                emit(item.steps)
                steps.append(
                    [(254, _UINT16, len(steps)), (1, _ENUM, _DURATION_REPEAT), (2, _UINT32, first), (4, _UINT32, item.count)]
                )

    emit(items)
    return steps


def write_fit(
    *,
    name: str,
    description: str | None,
    items: Sequence[WorkoutStep | RepeatBlock | InnerRepeat],
    context: ExportContext,
    created: datetime,
) -> bytes:
    steps = _steps(items, context)
    created_fit = int((created - FIT_EPOCH).total_seconds())
    body = _message(
        _FILE_ID,
        [
            (0, _ENUM, _FILE_WORKOUT),
            (1, _UINT16, _MANUFACTURER_DEVELOPMENT),
            (2, _UINT16, 0),
            (3, _UINT32Z, (zlib.crc32(name.encode()) ^ created_fit) & 0xFFFFFFFF or 1),
            (4, _UINT32, created_fit),
        ],
    )
    workout: list[Field] = [
        (4, _ENUM, _SPORT_CYCLING),
        (6, _UINT16, len(steps)),
        (8, _STRING, _text(" ".join(name.split()) or "Workout", MAX_NAME_BYTES)),
    ]
    if description and description.strip():
        workout.append((17, _STRING, _text(" ".join(description.split()), MAX_TEXT_BYTES)))
    body += _message(_WORKOUT, workout)
    for fields in steps:
        body += _message(_WORKOUT_STEP, fields)
    header = struct.pack("<BBHI4s", 14, 0x20, PROFILE_VERSION, len(body), b".FIT")
    header += struct.pack("<H", crc16(header))
    return header + body + struct.pack("<H", crc16(header + body))

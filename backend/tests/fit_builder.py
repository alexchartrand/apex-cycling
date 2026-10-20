"""A minimal FIT file writer for tests: just enough of the protocol (definition
and data messages, CRC) to build the recordings the parser has to read. No
real-device FIT file is committed, so this is also the format's reference here."""

import struct
from datetime import datetime, timezone

_FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)
_CRC_TABLE = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
              0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]  # fmt: skip

# base type id, struct format, "invalid" marker
_UINT8 = (0x02, "B", 0xFF)
_UINT16 = (0x84, "H", 0xFFFF)
_UINT32 = (0x86, "I", 0xFFFFFFFF)
_ENUM = (0x00, "B", 0xFF)

# message number -> field name -> (field number, base type, scale, offset)
_MESSAGES = {
    "file_id": (0, {"type": (0, _ENUM, 1, 0), "time_created": (4, _UINT32, 1, 0)}),
    "record": (
        20,
        {
            "timestamp": (253, _UINT32, 1, 0),
            "altitude": (2, _UINT16, 5, 500),
            "heart_rate": (3, _UINT8, 1, 0),
            "cadence": (4, _UINT8, 1, 0),
            "distance": (5, _UINT32, 100, 0),
            "speed": (6, _UINT16, 1000, 0),
            "power": (7, _UINT16, 1, 0),
        },
    ),
    "session": (
        18,
        {
            "timestamp": (253, _UINT32, 1, 0),
            "start_time": (2, _UINT32, 1, 0),
            "total_elapsed_time": (7, _UINT32, 1000, 0),
            "total_timer_time": (8, _UINT32, 1000, 0),
            "sport": (5, _ENUM, 1, 0),
        },
    ),
}


def crc16(data: bytes, crc: int = 0) -> int:
    for byte in data:
        for nibble in (byte & 0xF, byte >> 4):
            crc = ((crc >> 4) & 0x0FFF) ^ _CRC_TABLE[crc & 0xF] ^ _CRC_TABLE[nibble]
    return crc


def fit_time(moment: datetime) -> int:
    return int((moment - _FIT_EPOCH).total_seconds())


def _message(local_type: int, name: str, values: dict) -> bytes:
    """A definition message followed by one data message for `values`
    (None = field present but invalid, i.e. no reading)."""
    number, fields = _MESSAGES[name]
    used = [(field, fields[field]) for field in fields if field in values]
    definition = bytes([0x40 | local_type, 0, 0]) + struct.pack("<HB", number, len(used))
    data = bytes([local_type])
    for field, (field_number, (base_type, code, invalid), scale, offset) in used:
        definition += bytes([field_number, struct.calcsize(code), base_type])
        value = values[field]
        raw = invalid if value is None else round((value + offset) * scale)
        data += struct.pack("<" + code, raw)
    return definition + data


def build_fit(
    start: datetime,
    records: list[dict],
    *,
    timer_s: float | None = None,
    sport: int = 2,
    corrupt_crc: bool = False,
) -> bytes:
    """`records`: one dict per sample with `t` (seconds after `start`) and any
    of power, heart_rate, cadence (rpm), speed (m/s), distance (m), altitude (m)."""
    body = _message(0, "file_id", {"type": 4, "time_created": fit_time(start)})
    for record in records:
        values = {key: value for key, value in record.items() if key != "t"}
        values["timestamp"] = fit_time(start) + record["t"]
        body += _message(1, "record", values)
    elapsed = records[-1]["t"] if records else 0
    body += _message(
        2,
        "session",
        {
            "timestamp": fit_time(start) + elapsed,
            "start_time": fit_time(start),
            "total_elapsed_time": elapsed,
            "total_timer_time": timer_s if timer_s is not None else elapsed,
            "sport": sport,
        },
    )
    header = struct.pack("<BBHI4s", 14, 0x20, 2100, len(body), b".FIT")
    header += struct.pack("<H", crc16(header))
    crc = crc16(header + body)
    return header + body + struct.pack("<H", crc ^ 1 if corrupt_crc else crc)

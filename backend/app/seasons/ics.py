"""An iCalendar (RFC 5545) feed of planned sessions and races — pure. Every
entry is an all-day event: plans have a date, not a time of day."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

_CRLF = "\r\n"
_FOLD_OCTETS = 75


@dataclass(frozen=True)
class CalendarEntry:
    uid: str
    day: date
    summary: str
    description: str | None = None
    location: str | None = None


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Lines are at most 75 octets; a longer one continues on the next line after a space.
    Never splits inside a multi-byte character."""
    encoded = line.encode("utf-8")
    if len(encoded) <= _FOLD_OCTETS:
        return line
    parts: list[str] = []
    current = b""
    limit = _FOLD_OCTETS
    for char in line:
        piece = char.encode("utf-8")
        if len(current) + len(piece) > limit:
            parts.append(current.decode("utf-8"))
            current = b""
            limit = _FOLD_OCTETS - 1  # the continuation line starts with a space
        current += piece
    parts.append(current.decode("utf-8"))
    return (_CRLF + " ").join(parts)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_calendar(name: str, entries: Sequence[CalendarEntry], now: datetime) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ApexCycling//Training calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        # Hints for how often a subscriber should look again.
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for entry in entries:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{entry.uid}",
            f"DTSTAMP:{_stamp(now)}",
            f"DTSTART;VALUE=DATE:{entry.day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{entry.day + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_escape(entry.summary)}",
        ]
        if entry.description:
            lines.append(f"DESCRIPTION:{_escape(entry.description)}")
        if entry.location:
            lines.append(f"LOCATION:{_escape(entry.location)}")
        lines += ["TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return _CRLF.join(_fold(line) for line in lines) + _CRLF

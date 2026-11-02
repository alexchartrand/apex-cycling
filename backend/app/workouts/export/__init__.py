"""Workout files to download: `.fit` for head units, `.zwo` for Zwift,
`.erg`/`.mrc` for ERG apps. Pure; `workouts/export_service.py` gathers the
athlete's FTP and bests."""

import enum
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.workouts.export.common import ExportContext, NeedsFtp  # noqa: F401  (re-exported)
from app.workouts.export.erg import write_course
from app.workouts.export.fit import write_fit
from app.workouts.export.zwo import write_zwo
from app.workouts.schemas import InnerRepeat, RepeatBlock, WorkoutStep


class ExportFormat(str, enum.Enum):
    FIT = "fit"
    ZWO = "zwo"
    ERG = "erg"
    MRC = "mrc"


_MEDIA_TYPES = {
    ExportFormat.FIT: "application/vnd.ant.fit",
    ExportFormat.ZWO: "application/xml",
    ExportFormat.ERG: "text/plain",
    ExportFormat.MRC: "text/plain",
}


@dataclass(frozen=True)
class ExportFile:
    content: bytes
    filename: str
    media_type: str


def file_stem(name: str) -> str:
    """An ASCII file name: "Sprints lancés 3×200" → "sprints-lances-3-200"."""
    unaccented = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", unaccented.lower()).strip("-")[:60].rstrip("-") or "workout"


def export_workout(
    fmt: ExportFormat,
    *,
    name: str,
    description: str | None,
    tags: Sequence[str],
    items: Sequence[WorkoutStep | RepeatBlock | InnerRepeat],
    context: ExportContext,
    created: datetime,
) -> ExportFile:
    """Raises `NeedsFtp` (ERG/MRC only)."""
    if fmt is ExportFormat.FIT:
        content = write_fit(name=name, description=description, items=items, context=context, created=created)
    elif fmt is ExportFormat.ZWO:
        content = write_zwo(name=name, description=description, tags=tags, items=items, context=context)
    else:
        unit = "watts" if fmt is ExportFormat.ERG else "percent"
        content = write_course(unit=unit, name=name, description=description, items=items, context=context)
    return ExportFile(content, f"{file_stem(name)}.{fmt.value}", _MEDIA_TYPES[fmt])

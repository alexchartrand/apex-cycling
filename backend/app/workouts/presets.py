"""The built-in workouts everyone sees, from the hand-maintained
`presets.json` next to this module (part of the code: adding one is an edit
and a deploy). Every text — name, description, tags, a step's label and
notes — is `{"en": …, "fr": …}`; the rest is a workout's step tree as
stored. They aren't rows: each has a fixed id derived from its `key`, so
links and duplicates keep working across deploys as long as the key stays.
"""

import json
import uuid
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.notifications.messages import DEFAULT_LOCALE
from app.workouts.schemas import WorkoutWrite

PRESETS_FILE = Path(__file__).with_name("presets.json")
LOCALES = ("en", "fr")
_ID_NAMESPACE = uuid.UUID("5a7c3e0e-6f43-4c6b-9a43-2f0d4f1c2b90")


class InvalidPresetFile(Exception):
    pass


@dataclass(frozen=True)
class Preset:
    id: uuid.UUID
    key: str
    by_locale: dict[str, WorkoutWrite]

    def localized(self, locale: str | None) -> WorkoutWrite:
        return self.by_locale[locale if locale in self.by_locale else DEFAULT_LOCALE]


def preset_id(key: str) -> uuid.UUID:
    return uuid.uuid5(_ID_NAMESPACE, f"preset:{key}")


def _localize(value: Any, locale: str) -> Any:
    """Picks `locale` out of every `{"en", "fr"}` pair."""
    if isinstance(value, dict):
        if set(value) == set(LOCALES):
            return value[locale]
        return {k: _localize(v, locale) for k, v in value.items()}
    if isinstance(value, list):
        return [_localize(v, locale) for v in value]
    return value


def load_presets(path: Path) -> dict[uuid.UUID, Preset]:
    """Checked as a whole, in every language, so a typo fails the tests (and
    the first read) rather than showing a half-translated workout."""
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InvalidPresetFile(f"{path}: {exc}") from exc
    if not isinstance(entries, list):
        raise InvalidPresetFile(f"{path}: expected a list of workouts")
    presets: dict[uuid.UUID, Preset] = {}
    for entry in entries:
        key = entry.get("key") if isinstance(entry, dict) else None
        if not isinstance(key, str) or not key:
            raise InvalidPresetFile(f"{path}: every workout needs a key")
        body = {k: v for k, v in entry.items() if k != "key"}
        for field in ("name", "description", "tags"):
            if not (isinstance(body.get(field), dict) and set(body[field]) == set(LOCALES)):
                raise InvalidPresetFile(f"{key}: {field} needs exactly {', '.join(LOCALES)}")
        by_locale = {}
        for locale in LOCALES:
            try:
                by_locale[locale] = WorkoutWrite.model_validate(_localize(body, locale))
            except ValidationError as exc:
                raise InvalidPresetFile(f"{key} ({locale}): {exc}") from exc
        id_ = preset_id(key)
        if id_ in presets:
            raise InvalidPresetFile(f"{key}: duplicate key")
        presets[id_] = Preset(id=id_, key=key, by_locale=by_locale)
    return presets


@cache
def presets() -> dict[uuid.UUID, Preset]:
    """The presets of `PRESETS_FILE`, read once per process."""
    return load_presets(PRESETS_FILE)

"""The built-in workouts: the real file, its languages, and what a user may do with one."""

import json

import pytest

from app.workouts.presets import LOCALES, InvalidPresetFile, load_presets, preset_id, presets
from app.workouts.structure import estimate, is_track
from tests.test_aero_api import _setup


def test_the_shipped_presets_load_in_every_language():
    loaded = presets()
    assert len(loaded) >= 10
    for preset in loaded.values():
        en, fr = (preset.by_locale[locale] for locale in LOCALES)
        assert en.name != fr.name or en.name.startswith(("Sweet", "Endurance", "VO₂", "Tempo")), preset.key
        assert len(en.tags) == len(fr.tags), preset.key
        # Only the words differ: the same structure in both languages.
        assert estimate(en.steps).duration_s == estimate(fr.steps).duration_s, preset.key
        assert 10 * 60 <= estimate(en.steps).duration_s <= 3 * 3600, preset.key
    assert any(is_track(p.by_locale["en"].steps) for p in loaded.values())
    assert any(not is_track(p.by_locale["en"].steps) for p in loaded.values())


def _write(tmp_path, entries) -> object:
    path = tmp_path / "presets.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def _entry(**over) -> dict:
    return {
        "key": "easy",
        "name": {"en": "Easy", "fr": "Facile"},
        "description": {"en": "Spin", "fr": "Tourner"},
        "tags": {"en": ["recovery"], "fr": ["récupération"]},
        "steps": [{"duration_s": 600, "label": {"en": "Spin", "fr": "Tourner"}}],
        **over,
    }


def test_a_preset_reads_in_each_language_with_a_stable_id(tmp_path):
    loaded = load_presets(_write(tmp_path, [_entry()]))
    preset = loaded[preset_id("easy")]
    assert preset.localized("en").steps[0].label == "Spin"
    assert preset.localized("fr").steps[0].label == "Tourner"
    assert preset.localized(None).name == "Facile"  # French when no language is saved


@pytest.mark.parametrize(
    "entries",
    [
        {"not": "a list"},
        [_entry(key="")],
        [_entry(name={"en": "Only English"})],
        [_entry(steps=[{"duration_s": 600, "label": {"en": "Spin"}}])],  # half-translated label
        [_entry(steps=[{"duration_s": 600, "laps": 2}])],
        [_entry(), _entry()],  # same key twice
    ],
)
def test_a_bad_preset_file_is_refused(tmp_path, entries):
    with pytest.raises(InvalidPresetFile):
        load_presets(_write(tmp_path, entries))


async def test_presets_are_listed_in_my_language_and_duplicated_but_not_edited(client, db_session):
    await _setup(client, db_session, upload=False)
    key_id = str(preset_id("flying-200s"))

    listed = (await client.get("/workouts", params={"source": "preset"})).json()
    assert len(listed) == len(presets())
    flying = next(w for w in listed if w["id"] == key_id)
    assert flying["name"] == "200 m lancés"  # no saved language: French
    assert flying["source"] == "preset" and flying["can_edit"] is False and flying["owner_name"] is None
    assert flying["is_track"] is True and flying["created_at"] is None
    assert [w["id"] for w in (await client.get("/workouts", params={"q": "200 m lancé"})).json()] == [key_id]

    await client.patch("/auth/me/preferences", json={"locale": "en"})
    detail = (await client.get(f"/workouts/{key_id}")).json()
    assert detail["name"] == "Flying 200s" and detail["steps"][0]["label"] == "Warm-up"

    assert (await client.patch(f"/workouts/{key_id}", json={"name": "Mine now"})).status_code == 403
    assert (await client.delete(f"/workouts/{key_id}")).status_code == 403

    copy = await client.post(f"/workouts/{key_id}/duplicate")
    assert copy.status_code == 201, copy.text
    assert copy.json()["source"] == "mine" and copy.json()["can_edit"] is True
    assert copy.json()["name"] == "Flying 200s" and copy.json()["steps"] == detail["steps"]
    assert [w["name"] for w in (await client.get("/workouts", params={"source": "mine"})).json()] == ["Flying 200s"]
    # Mine first when a preset has the same name.
    same_name = [w["source"] for w in (await client.get("/workouts")).json() if w["name"] == "Flying 200s"]
    assert same_name == ["mine", "preset"]

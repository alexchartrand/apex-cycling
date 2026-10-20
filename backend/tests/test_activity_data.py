"""Imported-activity rows through the whole-account operations: export and
delete (the original files go with the rows, and only once the deletion
commits)."""

import csv
import io
import uuid
import zipfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.activities import storage, streams
from app.activities.models import Activity, ActivityPowerCurve, ActivitySource, ActivityStream
from app.core.config import get_settings
from tests.test_account import PASSWORD, _rows_referencing, _signup


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


async def _add_activity(db_session, athlete_id: uuid.UUID, content: bytes = b"<gpx/>") -> Activity:
    sha = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    path = storage.save_original(athlete_id, sha, "gpx", content)
    async with db_session() as session:
        activity = Activity(
            athlete_id=athlete_id,
            source=ActivitySource.UPLOAD,
            name="Morning ride",
            start_time=datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc),
            elapsed_s=3.0,
            has_power=True,
            file_path=path,
            file_format="gpx",
            file_sha256=sha,
        )
        session.add(activity)
        await session.flush()
        session.add(
            ActivityStream(
                activity_id=activity.id,
                sample_count=3,
                time_s=streams.pack("time_s", [0, 1, 2]),
                power_w=streams.pack("power_w", [100, None, 300]),
            )
        )
        session.add(ActivityPowerCurve(activity_id=activity.id, duration_s=1, power_w=300))
        await session.commit()
        return activity


async def test_export_includes_activities_and_their_samples(client, db_session):
    await _signup(client, "rider@example.com")
    athlete_id = uuid.UUID((await client.get("/athletes/me")).json()["id"])
    activity = await _add_activity(db_session, athlete_id)

    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))

    rows = list(csv.DictReader(io.StringIO(archive.read("activities.csv").decode())))
    assert [(r["name"], r["source"], r["has_power"]) for r in rows] == [("Morning ride", "upload", "True")]
    assert "file_path" in rows[0]  # a path on our disk, harmless
    curve = list(csv.DictReader(io.StringIO(archive.read("activity_power_curves.csv").decode())))
    assert [(c["duration_s"], c["power_w"]) for c in curve] == [("1", "300.0")]
    samples = list(csv.DictReader(io.StringIO(archive.read(f"activity_data/{activity.id}.csv").decode())))
    assert samples == [
        {"time_s": "0.0", "power_w": "100.0"},
        {"time_s": "1.0", "power_w": ""},
        {"time_s": "2.0", "power_w": "300.0"},
    ]


async def test_delete_account_removes_activities_and_original_files(client, db_session, uploads_dir):
    user = await _signup(client, "leaver@example.com")
    athlete_id = uuid.UUID((await client.get("/athletes/me")).json()["id"])
    activity = await _add_activity(db_session, athlete_id)
    assert (uploads_dir / activity.file_path).exists()

    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204

    async with db_session() as session:
        assert await _rows_referencing(session, uuid.UUID(user["id"]), athlete_id) == []
        for model in (Activity, ActivityStream, ActivityPowerCurve):
            assert (await session.scalars(select(model))).all() == []
    assert not (uploads_dir / activity.file_path).exists()
    assert not (uploads_dir / activity.file_path).parent.exists()


async def test_files_survive_a_rolled_back_deletion(db_session, uploads_dir):
    athlete_id = uuid.uuid4()
    path = storage.save_original(athlete_id, "a" * 64, "fit", b"data")

    async with db_session() as session:
        storage.delete_originals_after_commit(session, [path])
        await session.rollback()
    assert (uploads_dir / path).exists()

    async with db_session() as session:
        storage.delete_originals_after_commit(session, [path])
        await session.commit()
    assert not (uploads_dir / path).exists()


def test_stored_paths_cannot_escape_the_uploads_dir(uploads_dir):
    with pytest.raises(ValueError):
        storage.read_original("../../etc/passwd")


def test_save_original_is_named_by_athlete_and_hash(uploads_dir):
    athlete_id = uuid.uuid4()
    path = storage.save_original(athlete_id, "ab" * 32, ".FIT", b"x")
    assert path == f"activities/{athlete_id}/{'ab' * 32}.fit"
    assert storage.read_original(path) == b"x"

"""Original activity files (FIT/TCX/GPX) on the uploads volume.

The database keeps a path relative to `UPLOADS_DIR`, so the volume can move
without rewriting rows. Files are named by the athlete and the content hash,
which also makes a re-upload of the same bytes a no-op.
"""

import uuid
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

_ROOT = "activities"


def _resolve(relative_path: str) -> Path:
    root = Path(get_settings().uploads_dir).resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"path escapes the uploads directory: {relative_path}")
    return path


def relative_path_for(athlete_id: uuid.UUID, sha256: str, extension: str) -> str:
    return f"{_ROOT}/{athlete_id}/{sha256}.{extension.lstrip('.').lower()}"


def save_original(athlete_id: uuid.UUID, sha256: str, extension: str, content: bytes) -> str:
    """Writes the file (atomically) and returns the path to store."""
    relative = relative_path_for(athlete_id, sha256, extension)
    path = _resolve(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return relative


def read_original(relative_path: str) -> bytes:
    return _resolve(relative_path).read_bytes()


def delete_original(relative_path: str) -> None:
    _resolve(relative_path).unlink(missing_ok=True)


def delete_originals_after_commit(db: AsyncSession, relative_paths: list[str]) -> None:
    """Deletes the files once `db` commits, so a rolled-back deletion doesn't
    leave rows whose original file is gone."""
    if not relative_paths:
        return

    def remove(_session) -> None:
        for relative_path in relative_paths:
            delete_original(relative_path)

    event.listen(db.sync_session, "after_commit", remove, once=True)

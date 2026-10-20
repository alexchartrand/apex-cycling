"""Encryption at rest for third-party credentials (Strava tokens, Intervals.icu
API keys) stored in `DataSourceConnection.credentials`."""

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings

# The stored shape is {"enc": "<fernet token>"}; a dict without it is a row
# written before encryption existed and is read as-is (and encrypted the next
# time it is saved).
_ENVELOPE_KEY = "enc"


@lru_cache
def _fernet_for(keys: str) -> MultiFernet:
    parts = [part.strip() for part in keys.split(",") if part.strip()]
    if not parts:
        raise ValueError("DATA_ENCRYPTION_KEY is empty")
    return MultiFernet([Fernet(part) for part in parts])


def _fernet() -> MultiFernet:
    return _fernet_for(get_settings().data_encryption_key)


def encrypt_json(value: dict[str, Any]) -> dict[str, str]:
    token = _fernet().encrypt(json.dumps(value, separators=(",", ":")).encode())
    return {_ENVELOPE_KEY: token.decode()}


def decrypt_json(stored: dict[str, Any]) -> dict[str, Any]:
    if _ENVELOPE_KEY not in stored:
        return stored
    try:
        return json.loads(_fernet().decrypt(stored[_ENVELOPE_KEY].encode()))
    except InvalidToken as exc:
        raise ValueError(
            "Cannot decrypt stored credentials: DATA_ENCRYPTION_KEY differs from the key they were saved with"
        ) from exc


class EncryptedJSON(TypeDecorator):
    """A JSON column whose content is Fernet-encrypted. Stays a plain JSON
    column in the database, so adopting it needs no migration."""

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt_json(value)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt_json(value)

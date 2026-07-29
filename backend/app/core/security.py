import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

settings = get_settings()
_hasher = PasswordHasher()

ACCESS_COOKIE_NAME = "tt_access"
REFRESH_COOKIE_NAME = "tt_refresh"

# Precomputed at import time so login() can pay the same argon2 cost for a
# nonexistent email as for a wrong password, closing a timing side-channel
# that would otherwise let an attacker infer whether an email is registered.
DUMMY_PASSWORD_HASH = _hasher.hash("dummy-password-used-only-for-timing-safety")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


def _create_token(user_id: uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(user_id, TokenType.ACCESS, timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(user_id, TokenType.REFRESH, timedelta(days=settings.refresh_token_expire_days))


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: TokenType) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != expected_type.value:
        raise InvalidTokenError("unexpected token type")

    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("missing/invalid subject") from exc

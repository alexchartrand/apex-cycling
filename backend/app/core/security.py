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


def _create_token(
    user_id: uuid.UUID, token_type: TokenType, expires_delta: timedelta, extra_claims: dict | None = None
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(user_id, TokenType.ACCESS, timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(user_id: uuid.UUID, remember_me: bool = True) -> str:
    """`remember_me=False` mints a short-lived refresh token (session-only
    cookie on top, set by the router) so an unchecked login doesn't linger
    for the full remembered-session lifetime.
    """
    expires_delta = (
        timedelta(days=settings.refresh_token_expire_days)
        if remember_me
        else timedelta(hours=settings.refresh_token_expire_hours_default)
    )
    return _create_token(user_id, TokenType.REFRESH, expires_delta, extra_claims={"remember": remember_me})


class InvalidTokenError(Exception):
    pass


def _decode_payload(token: str, expected_type: TokenType) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != expected_type.value:
        raise InvalidTokenError("unexpected token type")
    return payload


def decode_token(token: str, expected_type: TokenType) -> uuid.UUID:
    payload = _decode_payload(token, expected_type)
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("missing/invalid subject") from exc


def decode_refresh_token(token: str) -> tuple[uuid.UUID, bool]:
    """Like `decode_token`, but also returns the `remember_me` choice the
    token was originally issued with, so `/auth/refresh` can re-issue cookies
    with matching persistence semantics.
    """
    payload = _decode_payload(token, TokenType.REFRESH)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("missing/invalid subject") from exc
    return user_id, bool(payload.get("remember", True))

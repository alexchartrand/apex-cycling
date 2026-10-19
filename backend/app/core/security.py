import hashlib
import secrets
import uuid
from dataclasses import dataclass
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


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    issued_at: datetime
    remember_me: bool


def decode_token(token: str, expected_type: TokenType) -> TokenClaims:
    """`remember_me` is only meaningful for refresh tokens: it's the choice
    the token was originally issued with, so `/auth/refresh` can re-issue
    cookies with matching persistence semantics."""
    payload = _decode_payload(token, expected_type)
    try:
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            issued_at=datetime.fromtimestamp(payload["iat"], timezone.utc),
            remember_me=bool(payload.get("remember", True)),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError("missing/invalid claims") from exc


def issued_before_credentials_change(issued_at: datetime, credentials_changed_at: datetime | None) -> bool:
    """True for a token minted before the user's last password change/reset,
    which must no longer work (that's what signs other devices out). JWT
    `iat` has one-second resolution, so compare at that resolution: the
    cookies re-issued in the same request as the change stay valid."""
    if credentials_changed_at is None:
        return False
    if credentials_changed_at.tzinfo is None:  # SQLite drops the offset
        credentials_changed_at = credentials_changed_at.replace(tzinfo=timezone.utc)
    return issued_at < credentials_changed_at.replace(microsecond=0)


def new_reset_token() -> tuple[str, str]:
    """A password-reset token and the hash to store: only the hash is kept,
    so a database leak doesn't hand out working reset links."""
    token = secrets.token_urlsafe(32)
    return token, hash_reset_token(token)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

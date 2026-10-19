from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import PasswordResetToken, User
from app.core.config import get_settings
from app.core.security import hash_password, hash_reset_token, new_reset_token


def set_password(user: User, new_password: str) -> None:
    """Also signs out every other session (see `issued_before_credentials_change`)."""
    user.hashed_password = hash_password(new_password)
    user.credentials_changed_at = datetime.now(timezone.utc)


async def create_reset_token(
    db: AsyncSession, user: User, ttl: timedelta, created_by: User | None = None
) -> tuple[str, datetime]:
    """Issues a new reset token, revoking any earlier unused one so only the
    latest link works. Returns the raw token (to send/show once) and expiry."""
    now = datetime.now(timezone.utc)
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    token, token_hash = new_reset_token()
    expires_at = now + ttl
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_by_user_id=created_by.id if created_by else None,
        )
    )
    return token, expires_at


async def find_valid_reset_token(db: AsyncSession, token: str) -> PasswordResetToken | None:
    row = await db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(token)))
    if row is None or row.used_at is not None:
        return None
    expires_at = row.expires_at
    if expires_at.tzinfo is None:  # SQLite drops the offset
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return None
    return row


def reset_link(token: str) -> str:
    # In the URL fragment, so the token never reaches server logs or a
    # Referer header; the SPA reads it client-side.
    return f"{get_settings().app_base_url.rstrip('/')}/reset-password#token={token}"


def reset_email(locale: str | None, link: str, expires_minutes: int) -> tuple[str, str]:
    """(subject, body) in the user's language, English by default."""
    if locale == "fr":
        return (
            "Réinitialiser votre mot de passe ApexCycling",
            "Bonjour,\n\n"
            "Quelqu'un (probablement vous) a demandé à réinitialiser le mot de passe de votre compte "
            "ApexCycling. Pour choisir un nouveau mot de passe, ouvrez ce lien :\n\n"
            f"{link}\n\n"
            f"Le lien expire dans {expires_minutes} minutes et ne fonctionne qu'une fois. "
            "Si vous n'avez rien demandé, ignorez ce courriel : votre mot de passe ne change pas.\n",
        )
    return (
        "Reset your ApexCycling password",
        "Hi,\n\n"
        "Someone (probably you) asked to reset the password of your ApexCycling account. "
        "To choose a new password, open this link:\n\n"
        f"{link}\n\n"
        f"The link expires in {expires_minutes} minutes and works once. "
        "If you didn't ask for this, ignore this email: your password stays the same.\n",
    )

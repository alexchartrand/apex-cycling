import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

# Keep in sync with frontend/src/features/auth/passwordPolicy.ts
MIN_PASSWORD_LENGTH = 12
MIN_CHARACTER_CLASSES = 3
_PASSWORD_CLASS_PATTERNS = (
    re.compile(r"[a-z]"),
    re.compile(r"[A-Z]"),
    re.compile(r"\d"),
    re.compile(r"[^a-zA-Z0-9]"),
)


Locale = Literal["fr", "en"]
ThemeMode = Literal["system", "light", "dark"]


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    # The UI choices made before signing up (emails also go out in `locale`).
    locale: Locale | None = None
    theme: ThemeMode | None = None

    @field_validator("password")
    @classmethod
    def _validate_password_strength(cls, value: str) -> str:
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
        classes_present = sum(1 for pattern in _PASSWORD_CLASS_PATTERNS if pattern.search(value))
        if classes_present < MIN_CHARACTER_CLASSES:
            raise ValueError(
                f"Password must contain at least {MIN_CHARACTER_CLASSES} of: "
                "lowercase letters, uppercase letters, numbers, symbols"
            )
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    is_platform_admin: bool
    locale: Locale | None
    theme: ThemeMode | None


class PreferencesUpdate(BaseModel):
    """Partial update: only the fields sent are changed."""

    locale: Locale | None = None
    theme: ThemeMode | None = None

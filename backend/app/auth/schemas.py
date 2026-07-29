import re
import uuid

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


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    is_platform_admin: bool

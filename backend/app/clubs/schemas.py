import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.athletes.schemas import Sex
from app.auth.schemas import Locale
from app.clubs.models import ClubRole
from app.training.efforts import StartType

# What an invite link may grant: admins are promoted in the member list, never
# through a link that gets forwarded around.
InviteRole = Literal[ClubRole.ATHLETE, ClubRole.COACH]


class ClubCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)


class ClubUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class ClubRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    # The requesting user's role in it.
    role: ClubRole


class MemberRead(BaseModel):
    id: uuid.UUID  # the membership
    user_id: uuid.UUID
    role: ClubRole
    display_name: str | None
    athlete_id: uuid.UUID | None
    # Only shown to club admins.
    email: EmailStr | None = None
    joined_at: datetime


class MemberUpdate(BaseModel):
    role: ClubRole


class RosterAthlete(BaseModel):
    id: uuid.UUID
    display_name: str
    user_id: uuid.UUID | None
    # No login: the club's admins run this profile.
    managed: bool
    birthdate: date | None
    sex: Sex | None
    # UCI age category code as of today (U11…U23, ELITE, M30…), null without a birthdate.
    category: str | None


class ManagedAthleteCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    birthdate: date | None = None
    sex: Sex | None = None
    height_cm: float | None = Field(default=None, gt=50, lt=260)


class InviteCreate(BaseModel):
    role: InviteRole = ClubRole.ATHLETE
    expires_in_days: int = Field(default=14, ge=1, le=90)
    # None = as many people as open the link before it expires.
    max_uses: int | None = Field(default=1, ge=1, le=1000)
    # Emails the link when SMTP is set up (otherwise the admin copies it).
    email: EmailStr | None = None
    locale: Locale | None = None


class InviteRead(BaseModel):
    id: uuid.UUID
    role: ClubRole
    expires_at: datetime
    max_uses: int | None
    use_count: int
    email: str | None
    created_at: datetime


class InviteCreated(InviteRead):
    """The only time the link is shown: only its hash is stored."""

    url: str
    emailed: bool


class InviteToken(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class InvitePreview(BaseModel):
    club_name: str
    role: ClubRole
    already_member: bool


class SqorzAccountLink(BaseModel):
    sqorz_account_id: str = Field(min_length=1, max_length=255)


class SqorzAccountRead(BaseModel):
    sqorz_account_id: str
    track_names: list[str]


class LeaderboardEntry(BaseModel):
    rank: int
    display_name: str
    time_ms: int
    achieved_on: date
    sex: Sex | None
    # UCI age category code (U19, ELITE, M35…) as of today; null without a birthdate.
    category: str | None
    source: Literal["sqorz", "manual"]
    is_me: bool


class Leaderboard(BaseModel):
    """The best time of each athlete who opted in, on one track, for one
    event and start. `participants` counts the opted-in athletes on the
    roster (with or without a time here); `categories` are the age categories
    present among the unfiltered entries, for the filter."""

    event_key: str
    start_type: StartType
    track_id: uuid.UUID
    track_name: str
    participants: int
    categories: list[str]
    entries: list[LeaderboardEntry]

import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.models import User
from app.clubs.models import Club, ClubInvite, ClubMembership, ClubRole, ClubSqorzAccount
from app.core.config import get_settings
from app.core.security import hash_reset_token, new_reset_token


class ClubError(Exception):
    """A request that's well-formed but not allowed in the club's current
    state; the router turns it into a 409 with this message."""


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:200] or "club"


async def unique_slug(db: AsyncSession, name: str) -> str:
    base = slugify(name)
    slug, n = base, 1
    while await db.scalar(select(Club.id).where(Club.slug == slug)) is not None:
        n += 1
        slug = f"{base}-{n}"
    return slug


async def self_athlete(db: AsyncSession, user_id: uuid.UUID) -> Athlete | None:
    return await db.scalar(select(Athlete).where(Athlete.user_id == user_id))


async def create_club(db: AsyncSession, user: User, name: str, timezone_name: str) -> Club:
    club = Club(name=name, slug=await unique_slug(db, name), timezone=timezone_name)
    db.add(club)
    await db.flush()
    db.add(ClubMembership(user_id=user.id, club_id=club.id, role=ClubRole.CLUB_ADMIN))
    await db.flush()
    return club


async def admin_count(db: AsyncSession, club_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count()).select_from(ClubMembership).where(
            ClubMembership.club_id == club_id, ClubMembership.role == ClubRole.CLUB_ADMIN
        )
    ) or 0


async def add_member(db: AsyncSession, user_id: uuid.UUID, club: Club, role: ClubRole) -> ClubMembership:
    """Adds the user to the club. Athletes are on a roster (`Athlete.club_id`),
    and a profile is on one club only, so joining as an athlete fails while
    the profile belongs to a different club. Doesn't commit."""
    if role == ClubRole.ATHLETE:
        athlete = await self_athlete(db, user_id)
        if athlete is not None:
            if athlete.club_id not in (None, club.id):
                raise ClubError("Your athlete profile already belongs to another club")
            athlete.club_id = club.id
    membership = ClubMembership(user_id=user_id, club_id=club.id, role=role)
    db.add(membership)
    await db.flush()
    return membership


async def change_role(db: AsyncSession, membership: ClubMembership, role: ClubRole) -> None:
    if membership.role == role:
        return
    if membership.role == ClubRole.CLUB_ADMIN and await admin_count(db, membership.club_id) <= 1:
        raise ClubError("A club needs at least one admin")
    athlete = await self_athlete(db, membership.user_id)
    if role == ClubRole.ATHLETE and athlete is not None:
        if athlete.club_id not in (None, membership.club_id):
            raise ClubError("This person's athlete profile already belongs to another club")
        athlete.club_id = membership.club_id
    elif membership.role == ClubRole.ATHLETE and athlete is not None and athlete.club_id == membership.club_id:
        athlete.club_id = None
        athlete.leaderboard_club_id = None  # leaving withdraws the consent for good
    membership.role = role
    await db.flush()


async def remove_member(db: AsyncSession, membership: ClubMembership) -> None:
    """Takes the person out of the club (their profile and data stay theirs,
    just off the roster). Doesn't commit."""
    if membership.role == ClubRole.CLUB_ADMIN and await admin_count(db, membership.club_id) <= 1:
        raise ClubError("A club needs at least one admin")
    athlete = await self_athlete(db, membership.user_id)
    if athlete is not None and athlete.club_id == membership.club_id:
        athlete.club_id = None
        athlete.leaderboard_club_id = None  # leaving withdraws the consent for good
    await db.delete(membership)
    await db.flush()


# --- invites -------------------------------------------------------------


def invite_link(token: str) -> str:
    # In the URL fragment, like password-reset links, so the token never
    # reaches server logs or a Referer header.
    return f"{get_settings().app_base_url.rstrip('/')}/join#token={token}"


def invite_email(locale: str | None, club_name: str, link: str, expires_in_days: int) -> tuple[str, str]:
    """(subject, body) in the recipient's language, English by default."""
    if locale == "fr":
        return (
            f"Invitation à rejoindre {club_name} sur ApexCycling",
            f"Bonjour,\n\nVous êtes invité(e) à rejoindre le club {club_name} sur ApexCycling. "
            f"Ouvrez ce lien pour accepter (créez un compte au besoin) :\n\n{link}\n\n"
            f"Le lien expire dans {expires_in_days} jours.\n",
        )
    return (
        f"You're invited to join {club_name} on ApexCycling",
        f"Hi,\n\nYou've been invited to join the club {club_name} on ApexCycling. "
        f"Open this link to accept (create an account if you need one):\n\n{link}\n\n"
        f"The link expires in {expires_in_days} days.\n",
    )


async def create_invite(
    db: AsyncSession,
    club: Club,
    created_by: User,
    *,
    role: ClubRole,
    expires_in_days: int,
    max_uses: int | None,
    email: str | None,
) -> tuple[ClubInvite, str]:
    """Returns the invite and the raw token (shown once). Doesn't commit."""
    token, token_hash = new_reset_token()
    invite = ClubInvite(
        club_id=club.id,
        token_hash=token_hash,
        role=role,
        expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
        max_uses=max_uses,
        email=email,
        created_by_user_id=created_by.id,
    )
    db.add(invite)
    await db.flush()
    return invite, token


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)  # SQLite drops the offset


def invite_usable(invite: ClubInvite) -> bool:
    if invite.revoked_at is not None or _aware(invite.expires_at) <= datetime.now(timezone.utc):
        return False
    return invite.max_uses is None or invite.use_count < invite.max_uses


async def find_usable_invite(db: AsyncSession, token: str) -> ClubInvite | None:
    invite = await db.scalar(select(ClubInvite).where(ClubInvite.token_hash == hash_reset_token(token)))
    return invite if invite is not None and invite_usable(invite) else None


async def accept_invite(db: AsyncSession, invite: ClubInvite, user: User) -> ClubMembership:
    """Joins the user to the invite's club in its role and uses one of its
    uses. Someone already in the club is left as they are (an invite never
    changes a role) and the link isn't used up. Doesn't commit."""
    existing = await db.scalar(
        select(ClubMembership).where(ClubMembership.user_id == user.id, ClubMembership.club_id == invite.club_id)
    )
    if existing is not None:
        return existing
    club = await db.get(Club, invite.club_id)
    membership = await add_member(db, user.id, club, invite.role)
    # Claim the use atomically so two people racing for the last one of a
    # limited link can't both get in.
    claimed = await db.execute(
        update(ClubInvite)
        .where(
            ClubInvite.id == invite.id,
            (ClubInvite.max_uses.is_(None)) | (ClubInvite.use_count < ClubInvite.max_uses),
        )
        .values(use_count=ClubInvite.use_count + 1)
    )
    if claimed.rowcount != 1:
        raise ClubError("This invite link has been used up")
    return membership


# --- accounts ------------------------------------------------------------


async def clubs_left_without_admin(db: AsyncSession, user: User) -> list[Club]:
    """Clubs the user is the only admin of that still have other people or
    managed athletes — deleting the account would orphan them."""
    mine = await db.scalars(
        select(ClubMembership.club_id).where(
            ClubMembership.user_id == user.id, ClubMembership.role == ClubRole.CLUB_ADMIN
        )
    )
    stuck = []
    for club_id in mine:
        if await admin_count(db, club_id) > 1:
            continue
        other_members = await db.scalar(
            select(func.count()).select_from(ClubMembership).where(
                ClubMembership.club_id == club_id, ClubMembership.user_id != user.id
            )
        )
        other_athletes = await db.scalar(
            select(func.count()).select_from(Athlete).where(
                Athlete.club_id == club_id, (Athlete.user_id.is_(None)) | (Athlete.user_id != user.id)
            )
        )
        if other_members or other_athletes:
            stuck.append(await db.get(Club, club_id))
    return stuck


async def delete_empty_clubs_of(db: AsyncSession, user: User) -> None:
    """Deletes the clubs the user is the sole member of (and their invites and
    facility links), after they've been cleared by `clubs_left_without_admin`.
    Their own athlete profile is taken off the roster first."""
    mine = list(await db.scalars(select(ClubMembership.club_id).where(ClubMembership.user_id == user.id)))
    for club_id in mine:
        others = await db.scalar(
            select(func.count()).select_from(ClubMembership).where(
                ClubMembership.club_id == club_id, ClubMembership.user_id != user.id
            )
        )
        if others:
            continue
        await db.execute(
            update(Athlete)
            .where((Athlete.club_id == club_id) | (Athlete.leaderboard_club_id == club_id))
            .values(club_id=None, leaderboard_club_id=None)
        )
        await db.execute(delete(ClubInvite).where(ClubInvite.club_id == club_id))
        await db.execute(delete(ClubSqorzAccount).where(ClubSqorzAccount.club_id == club_id))
        await db.execute(delete(ClubMembership).where(ClubMembership.club_id == club_id))
        await db.execute(delete(Club).where(Club.id == club_id))

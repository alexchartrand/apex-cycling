import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.athletes.models import Athlete
from app.athletes.schemas import AthleteRead
from app.auth.account import delete_athlete
from app.auth.deps import get_current_user, require_club_admin, require_club_member
from app.auth.models import User
from app.clubs.models import Club, ClubInvite, ClubMembership, ClubRole, ClubSqorzAccount
from app.clubs.schemas import (
    ClubCreate,
    ClubRead,
    ClubUpdate,
    InviteCreate,
    InviteCreated,
    InvitePreview,
    InviteRead,
    InviteToken,
    ManagedAthleteCreate,
    MemberRead,
    MemberUpdate,
    RosterAthlete,
    SqorzAccountLink,
    SqorzAccountRead,
)
from app.clubs.service import (
    ClubError,
    accept_invite,
    change_role,
    create_club,
    create_invite,
    find_usable_invite,
    invite_email,
    invite_link,
    remove_member,
)
from app.core.mail import mail_enabled, send_email
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.training.models import Track
from app.training.schemas import TrackSummary
from app.training.service import track_summary
from app.training.tracks_service import track_edit_rights

router = APIRouter(prefix="/clubs", tags=["clubs"])
invites_router = APIRouter(prefix="/invites", tags=["clubs"])


def _club_read(club: Club, role: ClubRole) -> ClubRead:
    return ClubRead(id=club.id, name=club.name, slug=club.slug, timezone=club.timezone, role=role)


def _conflict(exc: ClubError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post("", response_model=ClubRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def create(
    request: Request,
    payload: ClubCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClubRead:
    club = await create_club(db, current_user, payload.name.strip(), payload.timezone)
    await db.commit()
    return _club_read(club, ClubRole.CLUB_ADMIN)


@router.get("", response_model=list[ClubRead])
async def my_clubs(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ClubRead]:
    rows = await db.execute(
        select(Club, ClubMembership.role)
        .join(ClubMembership, ClubMembership.club_id == Club.id)
        .where(ClubMembership.user_id == current_user.id)
        .order_by(Club.name)
    )
    return [_club_read(club, role) for club, role in rows.all()]


@router.get("/{club_id}", response_model=ClubRead)
async def get_club(
    membership: ClubMembership = Depends(require_club_member), db: AsyncSession = Depends(get_db)
) -> ClubRead:
    return _club_read(await db.get(Club, membership.club_id), membership.role)


@router.patch("/{club_id}", response_model=ClubRead)
async def update_club(
    payload: ClubUpdate,
    membership: ClubMembership = Depends(require_club_admin),
    db: AsyncSession = Depends(get_db),
) -> ClubRead:
    club = await db.get(Club, membership.club_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{field} cannot be null")
        setattr(club, field, value.strip() if field == "name" else value)
    await db.commit()
    return _club_read(club, membership.role)


# --- members -------------------------------------------------------------


@router.get("/{club_id}/members", response_model=list[MemberRead])
async def list_members(
    membership: ClubMembership = Depends(require_club_member), db: AsyncSession = Depends(get_db)
) -> list[MemberRead]:
    rows = await db.execute(
        select(ClubMembership, User, Athlete)
        .join(User, User.id == ClubMembership.user_id)
        .outerjoin(Athlete, Athlete.user_id == User.id)
        .where(ClubMembership.club_id == membership.club_id)
        .order_by(ClubMembership.created_at)
    )
    is_admin = membership.role == ClubRole.CLUB_ADMIN
    return [
        MemberRead(
            id=m.id,
            user_id=user.id,
            role=m.role,
            display_name=athlete.display_name if athlete else None,
            athlete_id=athlete.id if athlete else None,
            email=user.email if is_admin else None,
            joined_at=m.created_at,
        )
        for m, user, athlete in rows.all()
    ]


async def _target_membership(db: AsyncSession, club_id: uuid.UUID, membership_id: uuid.UUID) -> ClubMembership:
    target = await db.get(ClubMembership, membership_id)
    if target is None or target.club_id != club_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return target


@router.patch("/{club_id}/members/{membership_id}", response_model=MemberUpdate)
async def update_member_role(
    membership_id: uuid.UUID,
    payload: MemberUpdate,
    membership: ClubMembership = Depends(require_club_admin),
    db: AsyncSession = Depends(get_db),
) -> MemberUpdate:
    target = await _target_membership(db, membership.club_id, membership_id)
    try:
        await change_role(db, target, payload.role)
    except ClubError as exc:
        raise _conflict(exc) from None
    await db.commit()
    return MemberUpdate(role=target.role)


@router.delete("/{club_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_club_member(
    membership_id: uuid.UUID,
    membership: ClubMembership = Depends(require_club_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    """An admin removes anyone; anyone can remove themselves (leave)."""
    target = await _target_membership(db, membership.club_id, membership_id)
    if target.id != membership.id and membership.role != ClubRole.CLUB_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Club admin access required")
    try:
        await remove_member(db, target)
    except ClubError as exc:
        raise _conflict(exc) from None
    await db.commit()


# --- roster and managed athletes ------------------------------------------


def _roster_athlete(athlete: Athlete) -> RosterAthlete:
    return RosterAthlete(
        id=athlete.id,
        display_name=athlete.display_name,
        user_id=athlete.user_id,
        managed=athlete.user_id is None,
        birthdate=athlete.birthdate,
        sex=athlete.sex,
    )


@router.get("/{club_id}/athletes", response_model=list[RosterAthlete])
async def roster(
    membership: ClubMembership = Depends(require_club_member), db: AsyncSession = Depends(get_db)
) -> list[RosterAthlete]:
    """Everyone on the club's athlete roster: members who joined as athletes
    and the managed profiles. For admins and coaches."""
    if membership.role == ClubRole.ATHLETE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach or club admin access required")
    athletes = await db.scalars(
        select(Athlete).where(Athlete.club_id == membership.club_id).order_by(Athlete.display_name)
    )
    return [_roster_athlete(a) for a in athletes]


@router.post("/{club_id}/athletes", response_model=AthleteRead, status_code=status.HTTP_201_CREATED)
async def add_managed_athlete(
    payload: ManagedAthleteCreate,
    membership: ClubMembership = Depends(require_club_admin),
    db: AsyncSession = Depends(get_db),
) -> Athlete:
    """A profile with no login (a junior, say) that the club's admins run:
    edit it and add transponders through the usual athlete endpoints."""
    athlete = Athlete(user_id=None, club_id=membership.club_id, **payload.model_dump())
    db.add(athlete)
    await db.commit()
    await db.refresh(athlete)
    return athlete


@router.delete("/{club_id}/athletes/{athlete_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_managed_athlete(
    athlete_id: uuid.UUID,
    membership: ClubMembership = Depends(require_club_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    athlete = await db.get(Athlete, athlete_id)
    if athlete is None or athlete.club_id != membership.club_id or athlete.user_id is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Managed athlete not found")
    await delete_athlete(db, athlete)
    await db.commit()


# --- invites ---------------------------------------------------------------


@router.get("/{club_id}/invites", response_model=list[InviteRead])
async def list_invites(
    membership: ClubMembership = Depends(require_club_admin), db: AsyncSession = Depends(get_db)
) -> list[ClubInvite]:
    """Links that can still be used (not revoked); expired ones included so
    the admin sees why one stopped working."""
    rows = await db.scalars(
        select(ClubInvite)
        .where(ClubInvite.club_id == membership.club_id, ClubInvite.revoked_at.is_(None))
        .order_by(ClubInvite.created_at.desc())
    )
    return list(rows)


@router.post("/{club_id}/invites", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
async def create_club_invite(
    payload: InviteCreate,
    background_tasks: BackgroundTasks,
    membership: ClubMembership = Depends(require_club_admin),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InviteCreated:
    club = await db.get(Club, membership.club_id)
    invite, token = await create_invite(
        db,
        club,
        current_user,
        role=payload.role,
        expires_in_days=payload.expires_in_days,
        max_uses=payload.max_uses,
        email=payload.email,
    )
    await db.commit()
    link = invite_link(token)
    emailed = payload.email is not None and mail_enabled()
    if emailed:
        subject, body = invite_email(payload.locale, club.name, link, payload.expires_in_days)
        background_tasks.add_task(send_email, payload.email, subject, body)
    return InviteCreated(**InviteRead.model_validate(invite, from_attributes=True).model_dump(), url=link, emailed=emailed)


@router.delete("/{club_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: uuid.UUID,
    membership: ClubMembership = Depends(require_club_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    invite = await db.get(ClubInvite, invite_id)
    if invite is None or invite.club_id != membership.club_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    invite.revoked_at = invite.revoked_at or datetime.now(timezone.utc)
    await db.commit()


# The token travels in the body, not the path, so it stays out of access logs.
_INVALID_INVITE = "This invite link is invalid, has expired or has been used up"


@invites_router.post("/preview", response_model=InvitePreview)
@limiter.limit("20/minute")
async def preview_invite(
    request: Request,
    payload: InviteToken,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitePreview:
    invite = await find_usable_invite(db, payload.token)
    if invite is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _INVALID_INVITE)
    club = await db.get(Club, invite.club_id)
    member = await db.scalar(
        select(ClubMembership.id).where(
            ClubMembership.user_id == current_user.id, ClubMembership.club_id == invite.club_id
        )
    )
    return InvitePreview(club_name=club.name, role=invite.role, already_member=member is not None)


@invites_router.post("/accept", response_model=ClubRead)
@limiter.limit("10/minute")
async def accept(
    request: Request,
    payload: InviteToken,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClubRead:
    invite = await find_usable_invite(db, payload.token)
    if invite is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _INVALID_INVITE)
    try:
        membership = await accept_invite(db, invite, current_user)
    except ClubError as exc:
        await db.rollback()
        raise _conflict(exc) from None
    await db.commit()
    return _club_read(await db.get(Club, invite.club_id), membership.role)


# --- facilities and tracks -------------------------------------------------


@router.get("/{club_id}/sqorz-accounts", response_model=list[SqorzAccountRead])
async def list_sqorz_accounts(
    membership: ClubMembership = Depends(require_club_member), db: AsyncSession = Depends(get_db)
) -> list[SqorzAccountRead]:
    account_ids = list(
        await db.scalars(
            select(ClubSqorzAccount.sqorz_account_id)
            .where(ClubSqorzAccount.club_id == membership.club_id)
            .order_by(ClubSqorzAccount.sqorz_account_id)
        )
    )
    result = []
    for account_id in account_ids:
        names = await db.scalars(select(Track.name).where(Track.sqorz_account_id == account_id).order_by(Track.name))
        result.append(SqorzAccountRead(sqorz_account_id=account_id, track_names=list(names)))
    return result


@router.post("/{club_id}/sqorz-accounts", response_model=SqorzAccountRead, status_code=status.HTTP_201_CREATED)
async def link_sqorz_account(
    club_id: uuid.UUID,
    payload: SqorzAccountLink,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SqorzAccountRead:
    """Platform admins only: linking hands the club's admins edit rights over
    that facility's (shared) tracks, so it isn't self-service."""
    if not current_user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform admin access required")
    if await db.get(Club, club_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found")
    account_id = payload.sqorz_account_id.strip()
    names = list(await db.scalars(select(Track.name).where(Track.sqorz_account_id == account_id).order_by(Track.name)))
    if not names:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No track has been imported for this sqorz account yet"
        )
    already = await db.scalar(
        select(ClubSqorzAccount.id).where(
            ClubSqorzAccount.club_id == club_id, ClubSqorzAccount.sqorz_account_id == account_id
        )
    )
    if already is None:
        db.add(ClubSqorzAccount(club_id=club_id, sqorz_account_id=account_id))
        await db.commit()
    return SqorzAccountRead(sqorz_account_id=account_id, track_names=names)


@router.delete("/{club_id}/sqorz-accounts/{sqorz_account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_sqorz_account(
    club_id: uuid.UUID,
    sqorz_account_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not current_user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform admin access required")
    link = await db.scalar(
        select(ClubSqorzAccount).where(
            ClubSqorzAccount.club_id == club_id, ClubSqorzAccount.sqorz_account_id == sqorz_account_id
        )
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    await db.delete(link)
    await db.commit()


@router.get("/{club_id}/tracks", response_model=list[TrackSummary])
async def club_tracks(
    membership: ClubMembership = Depends(require_club_member),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrackSummary]:
    """The tracks of the facilities this club is linked to, with whether the
    requesting user may edit each."""
    account_ids = select(ClubSqorzAccount.sqorz_account_id).where(ClubSqorzAccount.club_id == membership.club_id)
    tracks = await db.scalars(
        select(Track)
        .where(Track.sqorz_account_id.in_(account_ids))
        .options(selectinload(Track.views), selectinload(Track.loops))
        .order_by(Track.name)
    )
    rights = await track_edit_rights(db, current_user)
    return [track_summary(t, can_edit=rights.can_edit(t)) for t in tracks]

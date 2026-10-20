import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.account import build_export, delete_account
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetLink,
    PasswordResetRequest,
    PasswordResetRequested,
    PasswordResetTokenCheck,
    PasswordResetTokenInfo,
    PreferencesUpdate,
    SignupRequest,
    UserRead,
)
from app.auth.service import (
    create_reset_token,
    find_valid_reset_token,
    reset_email,
    reset_link,
    set_password,
)
from app.clubs.models import ClubMembership, ClubRole
from app.clubs.service import clubs_left_without_admin
from app.core.config import API_PREFIX, get_settings
from app.core.mail import mail_enabled, send_email
from app.core.rate_limit import limiter
from app.core.security import (
    ACCESS_COOKIE_NAME,
    DUMMY_PASSWORD_HASH,
    REFRESH_COOKIE_NAME,
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    issued_before_credentials_change,
    verify_password,
)
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _set_auth_cookies(response: Response, user_id, remember_me: bool = True) -> None:
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id, remember_me=remember_me)
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        # Unchecked "remember me": a browser-session cookie (no max_age) that's
        # gone once the browser closes, on top of the JWT's own shorter expiry.
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60 if remember_me else None,
        path=f"{API_PREFIX}/auth",
    )


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def signup(
    request: Request, payload: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        locale=payload.locale,
        theme=payload.theme,
    )
    db.add(user)
    await db.flush()

    # Every user gets their own athlete profile so they can self-report
    # transponder usage and see their own progression with zero club
    # involvement (see plan Context: "Account creation is fully open").
    athlete = Athlete(user_id=user.id, display_name=payload.display_name)
    db.add(athlete)

    await db.commit()
    await db.refresh(user)

    _set_auth_cookies(response, user.id)
    return user


@router.post("/login", response_model=UserRead)
@limiter.limit("10/minute")
async def login(
    request: Request, payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is not None:
        password_ok = verify_password(payload.password, user.hashed_password)
    else:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        password_ok = False
    if not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is inactive")

    _set_auth_cookies(response, user.id, remember_me=payload.remember_me)
    return user


@router.post("/refresh", response_model=UserRead)
async def refresh(
    response: Response,
    tt_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    if tt_refresh is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")

    try:
        claims = decode_token(tt_refresh, TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token") from exc

    user = await db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    if issued_before_credentials_change(claims.issued_at, user.credentials_changed_at):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session ended by a password change")

    _set_auth_cookies(response, user.id, remember_me=claims.remember_me)
    return user


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path=f"{API_PREFIX}/auth")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    _clear_auth_cookies(response)


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me/preferences", response_model=UserRead)
async def update_preferences(
    payload: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user


def _remember_me_from_cookie(tt_refresh: str | None) -> bool:
    """Keeps the current session's "remember me" choice when re-issuing cookies."""
    if tt_refresh is None:
        return False
    try:
        return decode_token(tt_refresh, TokenType.REFRESH).remember_me
    except InvalidTokenError:
        return False


# Wrong current password is a 400, not a 401: the SPA treats any 401 as an
# expired session and would try to refresh / bounce to the login page.
@router.post("/change-password", response_model=UserRead)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    response: Response,
    tt_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    set_password(current_user, payload.new_password)
    await db.commit()
    await db.refresh(current_user)
    # Every other session is now signed out; this one gets fresh cookies.
    _set_auth_cookies(response, current_user.id, remember_me=_remember_me_from_cookie(tt_refresh))
    return current_user


@router.post("/password-reset/request", response_model=PasswordResetRequested, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> PasswordResetRequested:
    """Emails a reset link when SMTP is configured. The answer never says
    whether the email is registered, and the send happens after the
    response so its timing doesn't either."""
    if not mail_enabled():
        return PasswordResetRequested(email_enabled=False)

    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is not None and user.is_active:
        minutes = settings.password_reset_expire_minutes
        token, _ = await create_reset_token(db, user, timedelta(minutes=minutes))
        await db.commit()
        subject, body = reset_email(user.locale, reset_link(token), minutes)
        background_tasks.add_task(send_email, user.email, subject, body)
    return PasswordResetRequested(email_enabled=True)


@router.post("/password-reset/check", response_model=PasswordResetTokenInfo)
@limiter.limit("20/minute")
async def check_password_reset_token(
    request: Request, payload: PasswordResetTokenCheck, db: AsyncSession = Depends(get_db)
) -> PasswordResetTokenInfo:
    row = await find_valid_reset_token(db, payload.token)
    user = await db.get(User, row.user_id) if row else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired")
    return PasswordResetTokenInfo(email=user.email)


@router.post("/password-reset/confirm", response_model=UserRead)
@limiter.limit("10/minute")
async def confirm_password_reset(
    request: Request, payload: PasswordResetConfirm, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    row = await find_valid_reset_token(db, payload.token)
    user = await db.get(User, row.user_id) if row else None
    if row is None or user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired")
    row.used_at = datetime.now(timezone.utc)
    set_password(user, payload.new_password)
    await db.commit()
    await db.refresh(user)
    _set_auth_cookies(response, user.id, remember_me=False)
    return user


async def _can_issue_reset_link(db: AsyncSession, admin: User, target: User) -> bool:
    """Platform admins: anyone. Club admins: members of a club they
    administer (by membership or athlete profile), but never another admin —
    a reset link is a takeover of that account, so it must not be a path to
    more privilege than the issuer already has."""
    if admin.is_platform_admin:
        return True
    if target.is_platform_admin or target.id == admin.id:
        return False
    target_is_admin = await db.scalar(
        select(ClubMembership.id).where(
            ClubMembership.user_id == target.id, ClubMembership.role == ClubRole.CLUB_ADMIN
        )
    )
    if target_is_admin is not None:
        return False
    admin_club_ids = select(ClubMembership.club_id).where(
        ClubMembership.user_id == admin.id, ClubMembership.role == ClubRole.CLUB_ADMIN
    )
    via_membership = await db.scalar(
        select(ClubMembership.id).where(
            ClubMembership.user_id == target.id, ClubMembership.club_id.in_(admin_club_ids)
        )
    )
    via_athlete = await db.scalar(
        select(Athlete.id).where(Athlete.user_id == target.id, Athlete.club_id.in_(admin_club_ids))
    )
    return via_membership is not None or via_athlete is not None


@router.post("/users/{user_id}/password-reset-link", response_model=PasswordResetLink)
async def create_password_reset_link(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PasswordResetLink:
    """The no-SMTP fallback: an admin generates a link to hand over."""
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not await _can_issue_reset_link(db, current_user, target):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to reset this user's password")
    token, expires_at = await create_reset_token(
        db, target, timedelta(hours=settings.password_reset_admin_expire_hours), created_by=current_user
    )
    await db.commit()
    return PasswordResetLink(url=reset_link(token), expires_at=expires_at)


@router.get("/me/export")
@limiter.limit("5/minute")
async def export_my_data(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    content = await build_export(db, current_user)
    filename = f"apexcycling-export-{date.today().isoformat()}.zip"
    return Response(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def delete_my_account(
    request: Request,
    payload: DeleteAccountRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password is incorrect")
    if stuck := await clubs_left_without_admin(db, current_user):
        names = ", ".join(club.name for club in stuck)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You are the only admin of {names}: make someone else an admin or remove its members first",
        )
    await delete_account(db, current_user)
    await db.commit()
    _clear_auth_cookies(response)

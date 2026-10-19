from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import LoginRequest, SignupRequest, UserRead
from app.core.config import API_PREFIX, get_settings
from app.core.rate_limit import limiter
from app.core.security import (
    ACCESS_COOKIE_NAME,
    DUMMY_PASSWORD_HASH,
    REFRESH_COOKIE_NAME,
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
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

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
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
        user_id, remember_me = decode_refresh_token(tt_refresh)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token") from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    _set_auth_cookies(response, user.id, remember_me=remember_me)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path=f"{API_PREFIX}/auth")


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

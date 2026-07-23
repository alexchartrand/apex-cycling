from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import LoginRequest, SignupRequest, UserRead
from app.core.config import get_settings
from app.core.security import (
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _set_auth_cookies(response: Response, user_id) -> None:
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
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
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/auth",
    )


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
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
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is inactive")

    _set_auth_cookies(response, user.id)
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
        user_id = decode_token(tt_refresh, TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token") from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    _set_auth_cookies(response, user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

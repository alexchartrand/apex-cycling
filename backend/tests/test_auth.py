from sqlalchemy import select

from app.athletes.models import Athlete
from app.auth.models import User


async def test_signup_creates_user_and_self_athlete(client, db_session):
    resp = await client.post(
        "/auth/signup",
        json={"email": "alex@example.com", "password": "Hunter2pass!23", "display_name": "Alex"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alex@example.com"
    assert "tt_access" in resp.cookies
    assert "tt_refresh" in resp.cookies

    async with db_session() as session:
        user = await session.scalar(select(User).where(User.email == "alex@example.com"))
        assert user is not None
        athlete = await session.scalar(select(Athlete).where(Athlete.user_id == user.id))
        assert athlete is not None
        assert athlete.club_ids == []
        assert athlete.display_name == "Alex"


async def test_signup_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "password": "Hunter2pass!23", "display_name": "Dup"}
    first = await client.post("/auth/signup", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/signup", json=payload)
    assert second.status_code == 409


async def test_login_and_me(client):
    await client.post(
        "/auth/signup",
        json={"email": "login@example.com", "password": "Correcthorse123!", "display_name": "Login Person"},
    )
    # /auth/me right after signup, using the cookie jar the client already has
    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "login@example.com"


async def test_login_wrong_password_rejected(client):
    await client.post(
        "/auth/signup",
        json={"email": "wrongpw@example.com", "password": "Correcthorse123!", "display_name": "Someone"},
    )
    resp = await client.post("/auth/login", json={"email": "wrongpw@example.com", "password": "nope"})
    assert resp.status_code == 401


async def test_me_requires_auth(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_refresh_issues_valid_access_token(client):
    await client.post(
        "/auth/signup",
        json={"email": "refresh@example.com", "password": "Correcthorse123!", "display_name": "Refresher"},
    )
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200
    assert resp.json()["email"] == "refresh@example.com"

    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "refresh@example.com"


async def test_refresh_requires_refresh_cookie(client):
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


async def test_logout_clears_cookies_and_blocks_me(client):
    await client.post(
        "/auth/signup",
        json={"email": "logout@example.com", "password": "Correcthorse123!", "display_name": "Logs Out"},
    )
    resp = await client.post("/auth/logout")
    assert resp.status_code == 204
    me = await client.get("/auth/me")
    assert me.status_code == 401


async def test_signup_rejects_short_password(client):
    resp = await client.post(
        "/auth/signup",
        json={"email": "short@example.com", "password": "Ab1!", "display_name": "Short"},
    )
    assert resp.status_code == 422


async def test_signup_rejects_password_missing_character_classes(client):
    resp = await client.post(
        "/auth/signup",
        json={"email": "weak@example.com", "password": "alllowercaseword", "display_name": "Weak"},
    )
    assert resp.status_code == 422


async def test_signup_accepts_strong_password(client):
    resp = await client.post(
        "/auth/signup",
        json={"email": "strong@example.com", "password": "Correcthorse123!", "display_name": "Strong"},
    )
    assert resp.status_code == 201


async def test_login_nonexistent_email_matches_wrong_password_response(client):
    await client.post(
        "/auth/signup",
        json={"email": "exists@example.com", "password": "Correcthorse123!", "display_name": "Someone"},
    )
    wrong_password = await client.post(
        "/auth/login", json={"email": "exists@example.com", "password": "nope-not-it"}
    )
    nonexistent_email = await client.post(
        "/auth/login", json={"email": "never-signed-up@example.com", "password": "nope-not-it"}
    )
    assert wrong_password.status_code == nonexistent_email.status_code == 401
    assert wrong_password.json()["detail"] == nonexistent_email.json()["detail"]

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.security import verify_password
from app.main import app


async def test_login_rate_limited_after_threshold(client):
    await client.post(
        "/auth/signup",
        json={"email": "rl-login@example.com", "password": "Correcthorse123!", "display_name": "RL"},
    )
    payload = {"email": "rl-login@example.com", "password": "wrong-password"}
    for _ in range(10):
        resp = await client.post("/auth/login", json=payload)
        assert resp.status_code == 401
    eleventh = await client.post("/auth/login", json=payload)
    assert eleventh.status_code == 429


async def test_signup_rate_limited_after_threshold(client):
    for i in range(5):
        resp = await client.post(
            "/auth/signup",
            json={
                "email": f"rl-signup-{i}@example.com",
                "password": "Correcthorse123!",
                "display_name": "RL",
            },
        )
        assert resp.status_code == 201
    sixth = await client.post(
        "/auth/signup",
        json={"email": "rl-signup-6@example.com", "password": "Correcthorse123!", "display_name": "RL"},
    )
    assert sixth.status_code == 429


async def test_login_rate_limit_is_per_ip(client, db_session):
    await client.post(
        "/auth/signup",
        json={"email": "rl-perip@example.com", "password": "Correcthorse123!", "display_name": "RL"},
    )
    payload = {"email": "rl-perip@example.com", "password": "wrong-password"}
    for _ in range(10):
        resp = await client.post("/auth/login", json=payload)
        assert resp.status_code == 401
    exhausted = await client.post("/auth/login", json=payload)
    assert exhausted.status_code == 429

    other_transport = ASGITransport(app=app, client=("10.0.0.5", 555))
    async with AsyncClient(transport=other_transport, base_url="http://test/api") as other_client:
        resp = await other_client.post("/auth/login", json=payload)
        assert resp.status_code == 401


async def test_cookie_secure_flag_reflects_settings(client, monkeypatch):
    import app.auth.router as auth_router_module

    monkeypatch.setattr(auth_router_module.settings, "cookie_secure", True)
    resp = await client.post(
        "/auth/signup",
        json={"email": "cookie-secure@example.com", "password": "Correcthorse123!", "display_name": "CS"},
    )
    set_cookie_headers = resp.headers.get_list("set-cookie")
    access_cookie_header = next(h for h in set_cookie_headers if h.startswith("tt_access="))
    assert "Secure" in access_cookie_header


async def test_cookie_not_secure_when_setting_disabled(client, monkeypatch):
    import app.auth.router as auth_router_module

    monkeypatch.setattr(auth_router_module.settings, "cookie_secure", False)
    resp = await client.post(
        "/auth/signup",
        json={"email": "cookie-insecure@example.com", "password": "Correcthorse123!", "display_name": "CI"},
    )
    set_cookie_headers = resp.headers.get_list("set-cookie")
    access_cookie_header = next(h for h in set_cookie_headers if h.startswith("tt_access="))
    assert "Secure" not in access_cookie_header


def test_cookie_secure_defaults_to_true(monkeypatch):
    # conftest sets COOKIE_SECURE=false in the environment so the test client's
    # http:// requests keep working; remove it here to check the class-level
    # default itself, not the test-session override.
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    assert Settings().cookie_secure is True


def test_verify_password_rejects_invalid_hash_without_500():
    assert verify_password("anything", "not-a-valid-argon2-hash") is False


def _refresh_cookie_header(resp) -> str:
    set_cookie_headers = resp.headers.get_list("set-cookie")
    return next(h for h in set_cookie_headers if h.startswith("tt_refresh="))


async def test_login_without_remember_me_sets_session_only_refresh_cookie(client):
    await client.post(
        "/auth/signup",
        json={"email": "no-remember@example.com", "password": "Correcthorse123!", "display_name": "NR"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "no-remember@example.com", "password": "Correcthorse123!", "remember_me": False},
    )
    assert resp.status_code == 200
    refresh_header = _refresh_cookie_header(resp)
    assert "max-age" not in refresh_header.lower()


async def test_login_with_remember_me_sets_persistent_refresh_cookie(client):
    await client.post(
        "/auth/signup",
        json={"email": "remember@example.com", "password": "Correcthorse123!", "display_name": "R"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "remember@example.com", "password": "Correcthorse123!", "remember_me": True},
    )
    assert resp.status_code == 200
    refresh_header = _refresh_cookie_header(resp)
    assert "max-age" in refresh_header.lower()


async def test_login_defaults_to_not_remembered(client):
    await client.post(
        "/auth/signup",
        json={"email": "default-remember@example.com", "password": "Correcthorse123!", "display_name": "D"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "default-remember@example.com", "password": "Correcthorse123!"},
    )
    assert resp.status_code == 200
    refresh_header = _refresh_cookie_header(resp)
    assert "max-age" not in refresh_header.lower()


async def test_refresh_preserves_remember_me_choice_across_reissue(client):
    await client.post(
        "/auth/signup",
        json={"email": "preserve-remember@example.com", "password": "Correcthorse123!", "display_name": "P"},
    )
    login_resp = await client.post(
        "/auth/login",
        json={
            "email": "preserve-remember@example.com",
            "password": "Correcthorse123!",
            "remember_me": False,
        },
    )
    assert "max-age" not in _refresh_cookie_header(login_resp).lower()

    refresh_resp = await client.post("/auth/refresh")
    assert refresh_resp.status_code == 200
    assert "max-age" not in _refresh_cookie_header(refresh_resp).lower()

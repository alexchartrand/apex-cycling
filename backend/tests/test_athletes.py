async def _signup(client, email, display_name="Someone"):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "Correcthorse123!", "display_name": display_name}
    )
    assert resp.status_code == 201
    return resp.json()


async def test_get_my_athlete_returns_self_profile(client, db_session):
    user = await _signup(client, "me@example.com", display_name="Me")

    resp = await client.get("/athletes/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user["id"]
    assert body["display_name"] == "Me"
    assert body["club_ids"] == []


async def test_get_my_athlete_requires_auth(client):
    resp = await client.get("/athletes/me")
    assert resp.status_code == 401

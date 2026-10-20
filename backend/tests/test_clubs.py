import uuid
from datetime import date, datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.athletes.models import Athlete
from app.auth.models import User
from app.clubs.models import Club, ClubInvite, ClubMembership, ClubSqorzAccount
from app.main import app
from app.training.models import Track
from tests.test_track_settings import _athlete_with_track

PASSWORD = "Correcthorse123!"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api")


async def _signup(client, email, name="Someone") -> dict:
    resp = await client.post("/auth/signup", json={"email": email, "password": PASSWORD, "display_name": name})
    assert resp.status_code == 201
    return resp.json()


async def _club(client, name="CNCB") -> dict:
    resp = await client.post("/clubs", json={"name": name, "timezone": "America/Toronto"})
    assert resp.status_code == 201
    return resp.json()


async def _invite(client, club_id, **body) -> dict:
    resp = await client.post(f"/clubs/{club_id}/invites", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _token(invite: dict) -> str:
    return invite["url"].split("#token=")[1]


async def _athlete_of(db_session, user_id: str) -> Athlete:
    async with db_session() as session:
        return await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(user_id)))


# --- clubs -----------------------------------------------------------------


async def test_creator_becomes_admin_and_slugs_stay_unique(client):
    await _signup(client, "founder@example.com")
    first = await _club(client, "Café Vélo")
    second = await _club(client, "Café Vélo")
    assert first["role"] == "club_admin"
    assert (first["slug"], second["slug"]) == ("cafe-velo", "cafe-velo-2")

    listed = (await client.get("/clubs")).json()
    assert [c["id"] for c in listed] == [first["id"], second["id"]]

    resp = await client.patch(f"/clubs/{first['id']}", json={"name": "Café Vélo Montréal"})
    assert resp.status_code == 200 and resp.json()["name"] == "Café Vélo Montréal"
    assert (await client.patch(f"/clubs/{first['id']}", json={"name": None})).status_code == 422


async def test_outsiders_cannot_see_or_touch_a_club(client):
    await _signup(client, "founder@example.com")
    club = await _club(client)
    async with _client() as outsider:
        await _signup(outsider, "outsider@example.com")
        assert (await outsider.get("/clubs")).json() == []
        for method, path in (
            ("get", f"/clubs/{club['id']}"),
            ("get", f"/clubs/{club['id']}/members"),
            ("get", f"/clubs/{club['id']}/tracks"),
        ):
            assert (await getattr(outsider, method)(path)).status_code == 404
        assert (await outsider.patch(f"/clubs/{club['id']}", json={"name": "Mine now"})).status_code == 403
        assert (await outsider.post(f"/clubs/{club['id']}/invites", json={})).status_code == 403


# --- invites ---------------------------------------------------------------


async def test_invite_link_joins_the_club_and_the_roster(client, db_session):
    await _signup(client, "admin@example.com")
    club = await _club(client)
    invite = await _invite(client, club["id"], role="athlete")
    assert invite["url"].startswith("http://localhost:5173/join#token=")
    assert invite["emailed"] is False

    async with _client() as joiner:
        user = await _signup(joiner, "joiner@example.com", "Joiner")
        preview = (await joiner.post("/invites/preview", json={"token": _token(invite)})).json()
        assert preview == {"club_name": "CNCB", "role": "athlete", "already_member": False}

        resp = await joiner.post("/invites/accept", json={"token": _token(invite)})
        assert resp.status_code == 200
        assert (resp.json()["id"], resp.json()["role"]) == (club["id"], "athlete")
        assert (await _athlete_of(db_session, user["id"])).club_id == uuid.UUID(club["id"])
        assert [c["id"] for c in (await joiner.get("/clubs")).json()] == [club["id"]]

        # One use: the link is spent for the next person, and the used count shows.
        async with _client() as late:
            await _signup(late, "late@example.com")
            assert (await late.post("/invites/accept", json={"token": _token(invite)})).status_code == 400
        [row] = (await client.get(f"/clubs/{club['id']}/invites")).json()
        assert row["use_count"] == 1

    roster = (await client.get(f"/clubs/{club['id']}/athletes")).json()
    assert [(a["display_name"], a["managed"]) for a in roster] == [("Joiner", False)]


async def test_an_invite_is_stored_hashed_and_does_not_change_existing_members(client, db_session):
    await _signup(client, "admin@example.com")
    club = await _club(client)
    invite = await _invite(client, club["id"], role="coach", max_uses=1)
    async with db_session() as session:
        stored = (await session.scalars(select(ClubInvite))).one()
        assert _token(invite) not in (stored.token_hash, str(stored.email))
        assert len(stored.token_hash) == 64

    # The admin opening their own coach link keeps their role and the use.
    preview = (await client.post("/invites/preview", json={"token": _token(invite)})).json()
    assert preview["already_member"] is True
    resp = await client.post("/invites/accept", json={"token": _token(invite)})
    assert (resp.status_code, resp.json()["role"]) == (200, "club_admin")
    assert (await client.get(f"/clubs/{club['id']}/invites")).json()[0]["use_count"] == 0


async def test_dead_invite_links_are_refused(client, db_session):
    await _signup(client, "admin@example.com")
    club = await _club(client)
    revoked = await _invite(client, club["id"])
    expired = await _invite(client, club["id"])
    unlimited = await _invite(client, club["id"], max_uses=None)
    rows = (await client.get(f"/clubs/{club['id']}/invites")).json()
    revoked_id = next(r["id"] for r in rows if r["id"] == revoked["id"])
    assert (await client.delete(f"/clubs/{club['id']}/invites/{revoked_id}")).status_code == 204
    async with db_session() as session:
        (await session.get(ClubInvite, uuid.UUID(expired["id"]))).expires_at = datetime.now(timezone.utc) - timedelta(
            minutes=1
        )
        await session.commit()

    async with _client() as joiner:
        await _signup(joiner, "joiner@example.com")
        for dead in (revoked, expired):
            assert (await joiner.post("/invites/preview", json={"token": _token(dead)})).status_code == 400
            assert (await joiner.post("/invites/accept", json={"token": _token(dead)})).status_code == 400
        assert (await joiner.post("/invites/accept", json={"token": "x" * 40})).status_code == 400
        assert (await joiner.post("/invites/accept", json={"token": _token(unlimited)})).status_code == 200

    ids = [r["id"] for r in (await client.get(f"/clubs/{club['id']}/invites")).json()]
    assert revoked["id"] not in ids


async def test_invite_links_cannot_grant_admin_and_need_an_admin_to_create(client):
    await _signup(client, "admin@example.com")
    club = await _club(client)
    assert (await client.post(f"/clubs/{club['id']}/invites", json={"role": "club_admin"})).status_code == 422
    assert (await client.post(f"/clubs/{club['id']}/invites", json={"expires_in_days": 0})).status_code == 422


async def test_invite_emails_go_out_when_smtp_is_set(client, monkeypatch):
    sent = []

    async def fake_send(to, subject, body):
        sent.append((to, subject, body))
        return True

    monkeypatch.setattr("app.clubs.router.mail_enabled", lambda: True)
    monkeypatch.setattr("app.clubs.router.send_email", fake_send)
    await _signup(client, "admin@example.com")
    club = await _club(client)
    invite = await _invite(client, club["id"], role="coach", email="new@example.com", locale="fr")
    assert invite["emailed"] is True
    [(to, subject, body)] = sent
    assert to == "new@example.com" and "CNCB" in subject and _token(invite) in body and "Bonjour" in body


async def test_athlete_in_another_club_cannot_join_as_an_athlete(client, db_session):
    await _signup(client, "admin@example.com")
    club_a = await _club(client, "Club A")
    club_b = await _club(client, "Club B")
    async with _client() as rider:
        await _signup(rider, "rider@example.com")
        invite_a = await _invite(client, club_a["id"], role="athlete", max_uses=5)
        invite_b = await _invite(client, club_b["id"], role="athlete", max_uses=5)
        coach_b = await _invite(client, club_b["id"], role="coach", max_uses=5)
        assert (await rider.post("/invites/accept", json={"token": _token(invite_a)})).status_code == 200
        resp = await rider.post("/invites/accept", json={"token": _token(invite_b)})
        assert resp.status_code == 409
        # Failed joins leave no half-membership behind; coaching elsewhere is fine.
        assert [c["id"] for c in (await rider.get("/clubs")).json()] == [club_a["id"]]
        assert (await rider.post("/invites/accept", json={"token": _token(coach_b)})).status_code == 200
    async with db_session() as session:
        assert (await session.scalars(select(ClubInvite).where(ClubInvite.id == uuid.UUID(invite_b["id"])))).one().use_count == 0


# --- members ---------------------------------------------------------------


async def _join(joiner, admin, club_id, role, **kw):
    invite = await _invite(admin, club_id, role=role, **kw)
    assert (await joiner.post("/invites/accept", json={"token": _token(invite)})).status_code == 200


async def test_member_list_roles_and_removal(client, db_session):
    await _signup(client, "admin@example.com", "Admin")
    club = await _club(client)
    async with _client() as coach, _client() as rider:
        await _signup(coach, "coach@example.com", "Coach")
        rider_user = await _signup(rider, "rider@example.com", "Rider")
        await _join(coach, client, club["id"], "coach")
        await _join(rider, client, club["id"], "athlete")

        as_admin = (await client.get(f"/clubs/{club['id']}/members")).json()
        assert [(m["display_name"], m["role"], m["email"]) for m in as_admin] == [
            ("Admin", "club_admin", "admin@example.com"),
            ("Coach", "coach", "coach@example.com"),
            ("Rider", "athlete", "rider@example.com"),
        ]
        as_rider = (await rider.get(f"/clubs/{club['id']}/members")).json()
        assert all(m["email"] is None for m in as_rider)
        # Coaches see the roster; athletes don't.
        assert [a["display_name"] for a in (await coach.get(f"/clubs/{club['id']}/athletes")).json()] == ["Rider"]
        assert (await rider.get(f"/clubs/{club['id']}/athletes")).status_code == 403

        rider_membership = next(m["id"] for m in as_admin if m["display_name"] == "Rider")
        coach_membership = next(m["id"] for m in as_admin if m["display_name"] == "Coach")
        admin_membership = next(m["id"] for m in as_admin if m["display_name"] == "Admin")

        # Only admins change roles or remove other people.
        assert (await rider.patch(f"/clubs/{club['id']}/members/{coach_membership}", json={"role": "athlete"})).status_code == 403
        assert (await rider.delete(f"/clubs/{club['id']}/members/{coach_membership}")).status_code == 403

        # The last admin can't demote or remove themselves...
        assert (await client.patch(f"/clubs/{club['id']}/members/{admin_membership}", json={"role": "coach"})).status_code == 409
        assert (await client.delete(f"/clubs/{club['id']}/members/{admin_membership}")).status_code == 409
        # ...until there's another.
        assert (await client.patch(f"/clubs/{club['id']}/members/{coach_membership}", json={"role": "club_admin"})).status_code == 200
        assert (await client.delete(f"/clubs/{club['id']}/members/{admin_membership}")).status_code == 204

        # Promoting an athlete takes them off the roster; the profile and data stay theirs.
        assert (await coach.patch(f"/clubs/{club['id']}/members/{rider_membership}", json={"role": "coach"})).status_code == 200
        assert (await _athlete_of(db_session, rider_user["id"])).club_id is None
        assert (await coach.patch(f"/clubs/{club['id']}/members/{rider_membership}", json={"role": "athlete"})).status_code == 200
        assert (await _athlete_of(db_session, rider_user["id"])).club_id == uuid.UUID(club["id"])

        # Leaving takes you off the roster too.
        assert (await rider.delete(f"/clubs/{club['id']}/members/{rider_membership}")).status_code == 204
        assert (await _athlete_of(db_session, rider_user["id"])).club_id is None
        assert (await rider.get(f"/clubs/{club['id']}")).status_code == 404
        assert (await coach.delete(f"/clubs/{club['id']}/members/{uuid.uuid4()}")).status_code == 404


# --- managed athletes --------------------------------------------------------


async def test_admin_runs_a_managed_athlete_end_to_end(client, db_session):
    await _signup(client, "admin@example.com")
    club = await _club(client)
    resp = await client.post(
        f"/clubs/{club['id']}/athletes",
        json={"display_name": "Junior", "birthdate": "2012-05-01", "sex": "male"},
    )
    assert resp.status_code == 201
    junior = resp.json()
    assert (junior["user_id"], junior["club_id"]) == (None, club["id"])
    assert junior["category"] is not None

    roster = (await client.get(f"/clubs/{club['id']}/athletes")).json()
    assert [(a["display_name"], a["managed"]) for a in roster] == [("Junior", True)]

    # The usual athlete endpoints work for the admin: profile, metrics, transponders.
    assert (await client.patch(f"/athletes/{junior['id']}", json={"display_name": "Junior B"})).status_code == 200
    assert (
        await client.post(f"/athletes/{junior['id']}/metrics", json={"effective_date": "2026-06-01", "weight_kg": 45})
    ).status_code == 201
    resp = await client.post(
        f"/athletes/{junior['id']}/transponder-assignments",
        json={"transponder_code": "ls-9", "start_date": date(2026, 6, 1).isoformat()},
    )
    assert resp.status_code == 201

    async with _client() as stranger:
        await _signup(stranger, "stranger@example.com")
        assert (await stranger.get(f"/athletes/{junior['id']}")).status_code == 403
        assert (await stranger.post(f"/clubs/{club['id']}/athletes", json={"display_name": "X"})).status_code == 403

    assert (await client.delete(f"/clubs/{club['id']}/athletes/{junior['id']}")).status_code == 204
    assert (await client.get(f"/athletes/{junior['id']}")).status_code == 404
    assert (await client.get(f"/clubs/{club['id']}/athletes")).json() == []


async def test_only_managed_athletes_of_the_club_can_be_deleted(client):
    await _signup(client, "admin@example.com")
    club = await _club(client)
    other = await _club(client, "Other")
    mine = (await client.get("/athletes/me")).json()
    junior = (await client.post(f"/clubs/{other['id']}/athletes", json={"display_name": "Junior"})).json()

    # A real person's profile, and another club's managed athlete, are both off limits.
    assert (await client.delete(f"/clubs/{club['id']}/athletes/{mine['id']}")).status_code == 404
    assert (await client.delete(f"/clubs/{club['id']}/athletes/{junior['id']}")).status_code == 404


# --- facilities and track editing ------------------------------------------------


async def test_club_admins_edit_the_tracks_of_linked_facilities(client, db_session):
    athlete_id = await _athlete_with_track(client, db_session, "rider@example.com")
    async with db_session() as session:
        account_id = (await session.scalars(select(Track.sqorz_account_id))).first()
        track_id = (await session.scalars(select(Track.id).where(Track.name == "Tour complet"))).first()

    async with _client() as admin, _client() as boss:
        await _signup(admin, "clubadmin@example.com")
        boss_user = await _signup(boss, "boss@example.com")
        async with db_session() as session:
            (await session.get(User, uuid.UUID(boss_user["id"]))).is_platform_admin = True
            await session.commit()
        club = await _club(admin)

        # Not linked yet: no edit, and the club has no tracks.
        assert (await admin.patch(f"/tracks/{track_id}", json={"length_m": 250})).status_code == 403
        assert (await admin.get(f"/clubs/{club['id']}/tracks")).json() == []

        # Linking is for platform admins, and only to facilities with imported tracks.
        body = {"sqorz_account_id": account_id}
        assert (await admin.post(f"/clubs/{club['id']}/sqorz-accounts", json=body)).status_code == 403
        assert (await boss.post(f"/clubs/{club['id']}/sqorz-accounts", json={"sqorz_account_id": "nope"})).status_code == 422
        resp = await boss.post(f"/clubs/{club['id']}/sqorz-accounts", json=body)
        assert resp.status_code == 201 and "Tour complet" in resp.json()["track_names"]
        assert (await boss.post(f"/clubs/{club['id']}/sqorz-accounts", json=body)).status_code == 201  # idempotent

        assert (await admin.get(f"/clubs/{club['id']}/sqorz-accounts")).json()[0]["sqorz_account_id"] == account_id
        tracks = (await admin.get(f"/clubs/{club['id']}/tracks")).json()
        assert {t["name"] for t in tracks} >= {"Tour complet"} and all(t["can_edit"] for t in tracks)

        assert (await admin.patch(f"/tracks/{track_id}", json={"length_m": 250})).status_code == 200
        # The athlete's own track list reflects it for the admin, not for the athlete.
        assert (await client.get(f"/athletes/{athlete_id}/tracks")).json()[0]["can_edit"] is False
        assert (await client.patch(f"/tracks/{track_id}", json={"length_m": 333})).status_code == 403

        # A plain member of the club can't edit.
        async with _client() as member:
            await _signup(member, "member@example.com")
            await _join(member, admin, club["id"], "athlete")
            assert (await member.patch(f"/tracks/{track_id}", json={"length_m": 333})).status_code == 403
            assert (await member.get(f"/clubs/{club['id']}/tracks")).json()[0]["can_edit"] is False

        # Unlinking takes the rights away again.
        assert (await admin.delete(f"/clubs/{club['id']}/sqorz-accounts/{account_id}")).status_code == 403
        assert (await boss.delete(f"/clubs/{club['id']}/sqorz-accounts/{account_id}")).status_code == 204
        assert (await boss.delete(f"/clubs/{club['id']}/sqorz-accounts/{account_id}")).status_code == 404
        assert (await admin.patch(f"/tracks/{track_id}", json={"length_m": 333})).status_code == 403


async def test_admin_of_one_club_cannot_edit_via_another_clubs_link(client, db_session):
    await _athlete_with_track(client, db_session, "rider@example.com")
    async with db_session() as session:
        account_id = (await session.scalars(select(Track.sqorz_account_id))).first()
        track_id = (await session.scalars(select(Track.id).where(Track.name == "Tour complet"))).first()
    async with _client() as other_admin:
        await _signup(other_admin, "other@example.com")
        await _club(other_admin, "Elsewhere")
        # A linked club somewhere else gives this admin nothing.
        await _signup(client, "linked@example.com")
        linked = await _club(client, "Linked")
        async with db_session() as session:
            session.add(ClubSqorzAccount(club_id=uuid.UUID(linked["id"]), sqorz_account_id=account_id))
            await session.commit()
        assert (await other_admin.patch(f"/tracks/{track_id}", json={"length_m": 250})).status_code == 403
        assert (await client.patch(f"/tracks/{track_id}", json={"length_m": 250})).status_code == 200


# --- account deletion ---------------------------------------------------------


async def test_the_only_admin_cannot_delete_their_account_while_the_club_has_people(client, db_session):
    await _signup(client, "admin@example.com")
    club = await _club(client)
    async with _client() as rider:
        await _signup(rider, "rider@example.com")
        await _join(rider, client, club["id"], "athlete")

        resp = await client.post("/auth/delete-account", json={"password": PASSWORD})
        assert resp.status_code == 409 and "CNCB" in resp.json()["detail"]
        assert (await client.get("/auth/me")).status_code == 200

        # With another admin in place, they can go; the club carries on.
        members = (await client.get(f"/clubs/{club['id']}/members")).json()
        rider_membership = next(m["id"] for m in members if m["email"] == "rider@example.com")
        await client.patch(f"/clubs/{club['id']}/members/{rider_membership}", json={"role": "club_admin"})
        assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
        assert (await rider.get(f"/clubs/{club['id']}")).json()["role"] == "club_admin"


async def test_deleting_the_account_of_a_one_person_club_removes_the_club(client, db_session):
    await _signup(client, "solo@example.com")
    club = await _club(client)
    await _invite(client, club["id"])
    assert (await client.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        assert await session.get(Club, uuid.UUID(club["id"])) is None
        assert (await session.scalars(select(ClubInvite))).all() == []
        assert (await session.scalars(select(ClubMembership))).all() == []


async def test_a_deleted_admin_leaves_their_invites_behind_untraced(client, db_session):
    await _signup(client, "boss@example.com")
    club = await _club(client)
    async with _client() as second:
        second_user = await _signup(second, "second@example.com")
        await _join(second, client, club["id"], "coach")
        members = (await client.get(f"/clubs/{club['id']}/members")).json()
        second_membership = next(m["id"] for m in members if m["email"] == "second@example.com")
        await client.patch(f"/clubs/{club['id']}/members/{second_membership}", json={"role": "club_admin"})
        await _invite(second, club["id"])
        assert (await second.post("/auth/delete-account", json={"password": PASSWORD})).status_code == 204
    async with db_session() as session:
        invites = (await session.scalars(select(ClubInvite).where(ClubInvite.club_id == uuid.UUID(club["id"])))).all()
        assert invites and all(i.created_by_user_id != uuid.UUID(second_user["id"]) for i in invites)


async def test_export_lists_club_memberships(client):
    import csv
    import io
    import zipfile

    await _signup(client, "admin@example.com")
    club = await _club(client)
    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    rows = list(csv.DictReader(io.StringIO(archive.read("club_memberships.csv").decode())))
    assert [(r["club_id"], r["role"]) for r in rows] == [(club["id"], "club_admin")]

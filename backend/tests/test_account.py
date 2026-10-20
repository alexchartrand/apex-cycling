import csv
import io
import json
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import app.auth.router as auth_router
from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus
from app.auth.models import PasswordResetToken, User
from app.clubs.models import Club, ClubMembership, ClubRole
from app.connections.models import DataSourceConnection, TransponderAssignment
from app.connections.service import create_transponder_assignment
from app.core.config import get_settings
from app.core.security import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, TokenType
from app.db.base import Base
from app.ingestion.sqorz.normalizer import normalize_snapshot
from app.main import app as real_app
from app.training.models import TrainingLap
from app.training.records_service import recompute_personal_records
from tests.test_training import _make_payload

PASSWORD = "Correcthorse123!"
NEW_PASSWORD = "Batterystaple456?"


def _other_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api")


async def _signup(client, email):
    resp = await client.post("/auth/signup", json={"email": email, "password": PASSWORD, "display_name": "Rider"})
    assert resp.status_code == 201
    return resp.json()


def _token_issued_in_the_past(user_id: str, token_type: TokenType, seconds_ago: int = 30) -> str:
    """A token as another device would hold it, minted before a password change."""
    settings = get_settings()
    issued = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    payload = {"sub": user_id, "type": token_type.value, "iat": issued, "exp": issued + timedelta(hours=1)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def mail_outbox(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    sent: list[tuple[str, str, str]] = []

    async def fake_send(to, subject, body):
        sent.append((to, subject, body))
        return True

    monkeypatch.setattr(auth_router, "send_email", fake_send)
    return sent


def _token_from(body: str) -> str:
    return body.split("#token=")[1].split()[0]


# --- change password -------------------------------------------------------


async def test_change_password_signs_out_other_sessions(client, db_session):
    user = await _signup(client, "rider@example.com")

    resp = await client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert resp.status_code == 200

    # This session got fresh cookies and keeps working.
    assert (await client.get("/auth/me")).status_code == 200

    async with _other_client() as other:
        other.cookies.set(ACCESS_COOKIE_NAME, _token_issued_in_the_past(user["id"], TokenType.ACCESS))
        assert (await other.get("/auth/me")).status_code == 401
        other.cookies.set(REFRESH_COOKIE_NAME, _token_issued_in_the_past(user["id"], TokenType.REFRESH))
        assert (await other.post("/auth/refresh")).status_code == 401

    async with _other_client() as other:
        bad = await other.post("/auth/login", json={"email": "rider@example.com", "password": PASSWORD})
        assert bad.status_code == 401
        ok = await other.post("/auth/login", json={"email": "rider@example.com", "password": NEW_PASSWORD})
        assert ok.status_code == 200


async def test_change_password_rejects_wrong_current_or_weak_new(client, db_session):
    await _signup(client, "rider@example.com")
    resp = await client.post("/auth/change-password", json={"current_password": "nope", "new_password": NEW_PASSWORD})
    assert resp.status_code == 400
    resp = await client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"})
    assert resp.status_code == 422


async def test_tokens_unaffected_without_a_password_change(client, db_session):
    user = await _signup(client, "rider@example.com")
    async with _other_client() as other:
        other.cookies.set(ACCESS_COOKIE_NAME, _token_issued_in_the_past(user["id"], TokenType.ACCESS))
        assert (await other.get("/auth/me")).status_code == 200


# --- password reset --------------------------------------------------------


async def test_reset_request_without_smtp_sends_nothing(client, db_session):
    await _signup(client, "rider@example.com")
    resp = await client.post("/auth/password-reset/request", json={"email": "rider@example.com"})
    assert resp.status_code == 202
    assert resp.json() == {"email_enabled": False}
    async with db_session() as session:
        assert await session.scalar(select(PasswordResetToken)) is None


async def test_reset_by_email_end_to_end(client, db_session, mail_outbox):
    await client.post(
        "/auth/signup",
        json={"email": "rider@example.com", "password": PASSWORD, "display_name": "R", "locale": "fr"},
    )

    async with _other_client() as anon:
        resp = await anon.post("/auth/password-reset/request", json={"email": "rider@example.com"})
        assert resp.status_code == 202
        assert resp.json() == {"email_enabled": True}
        assert len(mail_outbox) == 1
        to, subject, body = mail_outbox[0]
        assert to == "rider@example.com"
        assert "mot de passe" in subject  # in the user's language
        token = _token_from(body)

        resp = await anon.post("/auth/password-reset/check", json={"token": token})
        assert resp.json() == {"email": "rider@example.com"}

        resp = await anon.post("/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD})
        assert resp.status_code == 200
        # Logged in by the reset.
        assert (await anon.get("/auth/me")).json()["email"] == "rider@example.com"

        # Single use.
        resp = await anon.post("/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD})
        assert resp.status_code == 400

    async with _other_client() as other:
        resp = await other.post("/auth/login", json={"email": "rider@example.com", "password": NEW_PASSWORD})
        assert resp.status_code == 200


async def test_reset_request_for_unknown_email_looks_the_same(client, db_session, mail_outbox):
    resp = await client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert resp.status_code == 202
    assert resp.json() == {"email_enabled": True}
    assert mail_outbox == []


async def test_new_reset_request_revokes_the_previous_link(client, db_session, mail_outbox):
    await _signup(client, "rider@example.com")
    await client.post("/auth/password-reset/request", json={"email": "rider@example.com"})
    await client.post("/auth/password-reset/request", json={"email": "rider@example.com"})
    first, second = (_token_from(body) for _, _, body in mail_outbox)

    assert (await client.post("/auth/password-reset/check", json={"token": first})).status_code == 400
    assert (await client.post("/auth/password-reset/check", json={"token": second})).status_code == 200


async def test_expired_or_garbage_reset_token_is_rejected(client, db_session, mail_outbox):
    await _signup(client, "rider@example.com")
    await client.post("/auth/password-reset/request", json={"email": "rider@example.com"})
    token = _token_from(mail_outbox[0][2])

    async with db_session() as session:
        row = await session.scalar(select(PasswordResetToken))
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    for t in (token, "garbage"):
        resp = await client.post("/auth/password-reset/confirm", json={"token": t, "new_password": NEW_PASSWORD})
        assert resp.status_code == 400


async def test_reset_token_is_stored_hashed(client, db_session, mail_outbox):
    await _signup(client, "rider@example.com")
    await client.post("/auth/password-reset/request", json={"email": "rider@example.com"})
    token = _token_from(mail_outbox[0][2])
    async with db_session() as session:
        row = await session.scalar(select(PasswordResetToken))
        assert row.token_hash != token
        assert len(row.token_hash) == 64


# --- admin-generated reset links ------------------------------------------


async def _make_club_with(db_session, admin_email: str, member_emails: list[str], admin_member_emails=()):
    async with db_session() as session:
        club = Club(name="CNCB", slug="cncb")
        session.add(club)
        await session.flush()
        users = {u.email: u for u in await session.scalars(select(User))}
        session.add(ClubMembership(user_id=users[admin_email].id, club_id=club.id, role=ClubRole.CLUB_ADMIN))
        for email in member_emails:
            session.add(ClubMembership(user_id=users[email].id, club_id=club.id, role=ClubRole.ATHLETE))
        for email in admin_member_emails:
            session.add(ClubMembership(user_id=users[email].id, club_id=club.id, role=ClubRole.CLUB_ADMIN))
        await session.commit()


async def test_club_admin_can_issue_reset_link_for_a_member_only(client, db_session):
    async with _other_client() as member, _other_client() as co_admin, _other_client() as outsider:
        member_user = await _signup(member, "member@example.com")
        co_admin_user = await _signup(co_admin, "coadmin@example.com")
        outsider_user = await _signup(outsider, "outsider@example.com")
        await _signup(client, "admin@example.com")
        await _make_club_with(db_session, "admin@example.com", ["member@example.com"], ["coadmin@example.com"])

        resp = await client.post(f"/auth/users/{member_user['id']}/password-reset-link")
        assert resp.status_code == 200
        url = resp.json()["url"]
        assert url.startswith("http://localhost:5173/reset-password#token=")

        # The link works for the member.
        token = url.split("#token=")[1]
        assert (await outsider.post("/auth/password-reset/check", json={"token": token})).json() == {
            "email": "member@example.com"
        }

        # Not for another admin, someone outside the club, or by a non-admin.
        assert (await client.post(f"/auth/users/{co_admin_user['id']}/password-reset-link")).status_code == 403
        assert (await client.post(f"/auth/users/{outsider_user['id']}/password-reset-link")).status_code == 403
        assert (await member.post(f"/auth/users/{outsider_user['id']}/password-reset-link")).status_code == 403


async def test_club_admin_cannot_reset_a_platform_admin(client, db_session):
    async with _other_client() as boss:
        boss_user = await _signup(boss, "boss@example.com")
        await _signup(client, "admin@example.com")
        await _make_club_with(db_session, "admin@example.com", ["boss@example.com"])
        async with db_session() as session:
            (await session.get(User, uuid.UUID(boss_user["id"]))).is_platform_admin = True
            await session.commit()

        assert (await client.post(f"/auth/users/{boss_user['id']}/password-reset-link")).status_code == 403
        # The platform admin can issue one for anybody.
        admin_id = (await client.get("/auth/me")).json()["id"]
        assert (await boss.post(f"/auth/users/{admin_id}/password-reset-link")).status_code == 200


# --- export and delete ---------------------------------------------------


async def _signup_with_training(client, db_session, email: str, transponder: str) -> tuple[dict, uuid.UUID]:
    user = await _signup(client, email)
    athlete_id = uuid.UUID((await client.get("/athletes/me")).json()["id"])
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-06-01", "weight_kg": 70})
    async with db_session() as session:
        await create_transponder_assignment(
            session,
            athlete_id=athlete_id,
            transponder_code=transponder,
            start_date=date(2026, 6, 1),
            end_date=None,
            created_by_user_id=uuid.UUID(user["id"]),
            notes=None,
        )
        await session.commit()
    async with db_session() as session:
        await normalize_snapshot(session, _make_payload(transponder_code=transponder))
        await recompute_personal_records(session, athlete_id)
        await session.commit()
    manual = await client.post(
        f"/athletes/{athlete_id}/manual-results",
        json={"event_key": "500m", "start_type": "standing", "time_ms": 36000, "achieved_on": "2026-06-10", "venue": "Elsewhere"},
    )
    assert manual.status_code == 201
    return user, athlete_id


async def test_export_contains_profile_and_training_data(client, db_session):
    await _signup_with_training(client, db_session, "rider@example.com", "TP-X")

    resp = await client.get("/auth/me/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "attachment" in resp.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(archive.namelist())
    assert {"account.json", "metrics.csv", "sessions.csv", "laps.csv", "lap_splits.csv", "tracks.csv"} <= names
    assert {"records.csv", "manual_results.csv"} <= names

    account = json.loads(archive.read("account.json"))
    assert account["user"]["email"] == "rider@example.com"
    assert "hashed_password" not in account["user"]
    assert account["athlete"]["display_name"] == "Rider"

    laps = list(csv.DictReader(io.StringIO(archive.read("laps.csv").decode())))
    assert len(laps) == 2
    splits = list(csv.DictReader(io.StringIO(archive.read("lap_splits.csv").decode())))
    assert len(splits) == 6
    metrics = list(csv.DictReader(io.StringIO(archive.read("metrics.csv").decode())))
    assert metrics[0]["weight_kg"] == "70.0"
    records = list(csv.DictReader(io.StringIO(archive.read("records.csv").decode())))
    assert [r["event_key"] for r in records] == ["lap"]
    manual = list(csv.DictReader(io.StringIO(archive.read("manual_results.csv").decode())))
    assert [(m["event_key"], m["time_ms"]) for m in manual] == [("500m", "36000")]


async def _rows_referencing(session, user_id: uuid.UUID, athlete_id: uuid.UUID) -> list[str]:
    """Every row in any table whose FK points at this user or athlete."""
    found = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            for fk in column.foreign_keys:
                target = {"users": user_id, "athletes": athlete_id}.get(fk.column.table.name)
                if target is None:
                    continue
                count = len((await session.execute(select(table).where(column == target))).all())
                if count:
                    found.append(f"{table.name}.{column.name}")
    return found


async def test_delete_account_removes_everything_of_the_user(client, db_session):
    user, athlete_id = await _signup_with_training(client, db_session, "leaver@example.com", "TP-L")
    user_id = uuid.UUID(user["id"])

    async with _other_client() as stayer:
        # Someone else whose data must survive, with links to the leaver.
        stayer_user, stayer_athlete_id = await _signup_with_training(stayer, db_session, "stayer@example.com", "TP-S")
        async with db_session() as session:
            session.add(
                CoachAthlete(
                    coach_user_id=user_id,
                    athlete_id=stayer_athlete_id,
                    initiated_by_user_id=user_id,
                    status=CoachAthleteStatus.ACTIVE,
                )
            )
            # An assignment the leaver entered for the stayer (e.g. as admin).
            stayer_assignment = await session.scalar(
                select(TransponderAssignment).where(TransponderAssignment.athlete_id == stayer_athlete_id)
            )
            stayer_assignment.created_by_user_id = user_id
            await session.commit()

        resp = await client.post("/auth/delete-account", json={"password": "wrong"})
        assert resp.status_code == 400

        resp = await client.post("/auth/delete-account", json={"password": PASSWORD})
        assert resp.status_code == 204
        assert (await client.get("/auth/me")).status_code == 401

        async with db_session() as session:
            assert await _rows_referencing(session, user_id, athlete_id) == []
            assert await session.get(User, user_id) is None
            assert await session.get(Athlete, athlete_id) is None
            # The stayer keeps all their data; the shared transponder pool stays.
            stayer_laps = (await session.scalars(select(TrainingLap).where(TrainingLap.athlete_id == stayer_athlete_id))).all()
            assert len(stayer_laps) == 2
            assert (await session.get(TransponderAssignment, stayer_assignment.id)).created_by_user_id is None
            assert len((await session.scalars(select(DataSourceConnection))).all()) == 2

        assert (await stayer.get("/athletes/me")).status_code == 200
        # The email is free again.
        async with _other_client() as again:
            await _signup(again, "leaver@example.com")

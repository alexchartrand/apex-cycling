import uuid

from fastapi import APIRouter, Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus
from app.auth.deps import require_athlete_access
from app.auth.models import User
from app.clubs.models import Club, ClubMembership, ClubRole
from app.main import app as real_app


# A tiny probe route mounted only for this test module, exercising
# require_athlete_access exactly as a real "GET /athletes/{athlete_id}/..."
# endpoint would. Included via `include_router` (not a separate FastAPI app
# whose routes get spliced in) so it's actually bound to `real_app`'s
# dependency_overrides -- FastAPI fixes a route's override-resolution to
# whichever app object created/included it at definition time.
probe_router = APIRouter()


@probe_router.get("/probe/{athlete_id}")
async def probe(athlete=Depends(require_athlete_access)):
    return {"athlete_id": str(athlete.id)}


real_app.include_router(probe_router)


async def _signup(client, email, display_name="Someone"):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "correcthorse", "display_name": display_name}
    )
    assert resp.status_code == 201
    return resp.json()


async def test_athlete_can_access_own_data(client, db_session):
    await _signup(client, "self@example.com")

    async with db_session() as session:
        athlete = await session.scalar(select(Athlete))

    resp = await client.get(f"/probe/{athlete.id}")
    assert resp.status_code == 200
    assert resp.json()["athlete_id"] == str(athlete.id)


async def test_unrelated_user_cannot_access_athlete(client, db_session):
    await _signup(client, "owner@example.com")

    other_client_transport = ASGITransport(app=real_app)
    async with AsyncClient(transport=other_client_transport, base_url="http://test") as other_client:
        await _signup(other_client, "stranger@example.com")

        async with db_session() as session:
            owner_athlete = await session.scalar(
                select(Athlete).join(User, Athlete.user_id == User.id).where(User.email == "owner@example.com")
            )

        resp = await other_client.get(f"/probe/{owner_athlete.id}")
        assert resp.status_code == 403


async def test_coach_with_active_link_can_access_athlete(client, db_session):
    athlete_data = await _signup(client, "coached@example.com")

    coach_transport = ASGITransport(app=real_app)
    async with AsyncClient(transport=coach_transport, base_url="http://test") as coach_client:
        coach_data = await _signup(coach_client, "coach@example.com")

        async with db_session() as session:
            athlete = await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(athlete_data["id"])))
            link = CoachAthlete(
                coach_user_id=uuid.UUID(coach_data["id"]),
                athlete_id=athlete.id,
                initiated_by_user_id=uuid.UUID(coach_data["id"]),
                status=CoachAthleteStatus.ACTIVE,
            )
            session.add(link)
            await session.commit()

        resp = await coach_client.get(f"/probe/{athlete.id}")
        assert resp.status_code == 200


async def test_coach_with_pending_link_cannot_access_athlete(client, db_session):
    athlete_data = await _signup(client, "pending-athlete@example.com")

    coach_transport = ASGITransport(app=real_app)
    async with AsyncClient(transport=coach_transport, base_url="http://test") as coach_client:
        coach_data = await _signup(coach_client, "pending-coach@example.com")

        async with db_session() as session:
            athlete = await session.scalar(
                select(Athlete).where(Athlete.user_id == uuid.UUID(athlete_data["id"]))
            )
            link = CoachAthlete(
                coach_user_id=uuid.UUID(coach_data["id"]),
                athlete_id=athlete.id,
                initiated_by_user_id=uuid.UUID(coach_data["id"]),
                status=CoachAthleteStatus.PENDING_ATHLETE_ACCEPTANCE,
            )
            session.add(link)
            await session.commit()

        resp = await coach_client.get(f"/probe/{athlete.id}")
        assert resp.status_code == 403


async def test_club_admin_can_access_managed_athlete_without_login(client, db_session):
    admin_data = await _signup(client, "admin@example.com")

    async with db_session() as session:
        club = Club(name="CNCB", slug="cncb")
        session.add(club)
        await session.flush()

        membership = ClubMembership(
            user_id=uuid.UUID(admin_data["id"]), club_id=club.id, role=ClubRole.CLUB_ADMIN
        )
        session.add(membership)

        junior = Athlete(user_id=None, club_id=club.id, display_name="Junior Athlete")
        session.add(junior)
        await session.commit()
        junior_id = junior.id

    resp = await client.get(f"/probe/{junior_id}")
    assert resp.status_code == 200

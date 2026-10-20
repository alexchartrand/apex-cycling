import uuid

from sqlalchemy import select

from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus
from tests.test_clubs import _client, _club, _join, _signup


async def _my_athlete_id(client) -> str:
    return (await client.get("/athletes/me")).json()["id"]


async def _setup(client):
    """`client` is the club admin; returns the club plus a coach and a rider in it."""
    admin = await _signup(client, "admin@example.com", "Admin")
    club = await _club(client)
    coach_client, rider_client = _client(), _client()
    coach = await _signup(coach_client, "coach@example.com", "Coach")
    rider = await _signup(rider_client, "rider@example.com", "Rider")
    await _join(coach_client, client, club["id"], "coach")
    await _join(rider_client, client, club["id"], "athlete")
    rider_athlete = await _my_athlete_id(rider_client)
    return club, admin, (coach_client, coach), (rider_client, rider), rider_athlete


async def _close(*clients):
    for c in clients:
        await c.aclose()


async def test_coach_asks_athlete_accepts_and_then_the_coach_has_access(client):
    club, _, (coach_c, coach), (rider_c, rider), rider_athlete = await _setup(client)
    try:
        resp = await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_id": rider_athlete})
        assert (resp.status_code, resp.json()) == (202, {"requested": True})

        # Pending: no access yet; the coach sees it waiting, the athlete has it in the inbox.
        assert (await coach_c.get(f"/athletes/{rider_athlete}")).status_code == 403
        [waiting] = (await coach_c.get("/coach-links/athletes")).json()
        assert (waiting["status"], waiting["needs_my_response"], waiting["initiated_by_me"]) == (
            "pending_athlete_acceptance",
            False,
            True,
        )
        assert (await coach_c.get("/coach-links/inbox")).json() == []
        [request] = (await rider_c.get("/coach-links/inbox")).json()
        assert (request["coach_name"], request["needs_my_response"]) == ("Coach", True)

        # The coach can't answer their own request.
        assert (await coach_c.post(f"/coach-links/{request['id']}/accept")).status_code == 403

        accepted = (await rider_c.post(f"/coach-links/{request['id']}/accept")).json()
        assert (accepted["status"], accepted["needs_my_response"]) == ("active", False)
        assert (await coach_c.get(f"/athletes/{rider_athlete}")).status_code == 200
        assert (await rider_c.get("/coach-links/inbox")).json() == []
        [mine] = (await rider_c.get("/coach-links/coaches")).json()
        assert (mine["coach_name"], mine["status"]) == ("Coach", "active")
        [theirs] = (await coach_c.get("/coach-links/athletes")).json()
        assert (theirs["athlete_name"], theirs["status"]) == ("Rider", "active")
        # Accepting twice is a conflict, not a silent no-op.
        assert (await rider_c.post(f"/coach-links/{request['id']}/accept")).status_code == 409
    finally:
        await _close(coach_c, rider_c)


async def test_athlete_asks_a_coach_of_their_club(client):
    club, _, (coach_c, coach), (rider_c, rider), rider_athlete = await _setup(client)
    try:
        resp = await rider_c.post("/coach-links", json={"acting_as": "athlete", "coach_user_id": coach["id"]})
        assert resp.status_code == 202
        [request] = (await coach_c.get("/coach-links/inbox")).json()
        assert (request["athlete_name"], request["needs_my_response"]) == ("Rider", True)
        assert (await coach_c.get(f"/athletes/{rider_athlete}")).status_code == 403
        # The athlete can't accept their own request.
        assert (await rider_c.post(f"/coach-links/{request['id']}/accept")).status_code == 403

        assert (await coach_c.post(f"/coach-links/{request['id']}/accept")).status_code == 200
        assert (await coach_c.get(f"/athletes/{rider_athlete}")).status_code == 200
    finally:
        await _close(coach_c, rider_c)


async def test_asking_each_other_activates_the_link(client, db_session):
    _, _, (coach_c, coach), (rider_c, rider), rider_athlete = await _setup(client)
    try:
        await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_id": rider_athlete})
        await rider_c.post("/coach-links", json={"acting_as": "athlete", "coach_user_id": coach["id"]})
        assert (await coach_c.get(f"/athletes/{rider_athlete}")).status_code == 200
        # Asking again once linked is refused; asking twice while pending is a no-op.
        resp = await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_id": rider_athlete})
        assert resp.status_code == 409
        async with db_session() as session:
            assert len((await session.scalars(select(CoachAthlete))).all()) == 1
    finally:
        await _close(coach_c, rider_c)


async def test_decline_revoke_and_ask_again(client):
    _, _, (coach_c, coach), (rider_c, rider), rider_athlete = await _setup(client)
    try:
        ask = {"acting_as": "coach", "athlete_id": rider_athlete}
        await coach_c.post("/coach-links", json=ask)
        [request] = (await rider_c.get("/coach-links/inbox")).json()
        assert (await rider_c.post(f"/coach-links/{request['id']}/revoke")).status_code == 204  # decline
        assert (await rider_c.get("/coach-links/inbox")).json() == []
        assert (await coach_c.get("/coach-links/athletes")).json() == []
        assert (await coach_c.get(f"/athletes/{rider_athlete}")).status_code == 403

        # Asking again reopens the same link; accepting gives access, revoking takes it away.
        await coach_c.post("/coach-links", json=ask)
        [again] = (await rider_c.get("/coach-links/inbox")).json()
        assert again["id"] == request["id"]
        await rider_c.post(f"/coach-links/{again['id']}/accept")
        assert (await coach_c.get(f"/athletes/{rider_athlete}")).status_code == 200
        assert (await rider_c.post(f"/coach-links/{again['id']}/revoke")).status_code == 204
        assert (await coach_c.get(f"/athletes/{rider_athlete}")).status_code == 403
        # Revoking is idempotent; the coach could also have ended it.
        assert (await coach_c.post(f"/coach-links/{again['id']}/revoke")).status_code == 204

        # Strangers learn nothing: same answer as for a link that doesn't exist.
        async with _client() as stranger:
            await _signup(stranger, "stranger@example.com")
            for link_id in (again["id"], str(uuid.uuid4())):
                assert (await stranger.post(f"/coach-links/{link_id}/revoke")).status_code == 404
                assert (await stranger.post(f"/coach-links/{link_id}/accept")).status_code == 404
    finally:
        await _close(coach_c, rider_c)


async def test_a_coach_can_cancel_their_own_pending_request(client):
    _, _, (coach_c, coach), (rider_c, rider), rider_athlete = await _setup(client)
    try:
        await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_id": rider_athlete})
        [waiting] = (await coach_c.get("/coach-links/athletes")).json()
        assert (await coach_c.post(f"/coach-links/{waiting['id']}/revoke")).status_code == 204
        assert (await rider_c.get("/coach-links/inbox")).json() == []
        assert (await rider_c.post(f"/coach-links/{waiting['id']}/accept")).status_code == 409
    finally:
        await _close(coach_c, rider_c)


async def test_picking_someone_from_a_club_is_limited_to_that_club(client):
    _, _, (coach_c, coach), (rider_c, rider), rider_athlete = await _setup(client)
    try:
        async with _client() as outsider:
            outsider_user = await _signup(outsider, "outsider@example.com", "Outsider")
            outsider_athlete = await _my_athlete_id(outsider)
            # A coach can't ask for an athlete outside their clubs; an athlete can't pick a stranger.
            resp = await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_id": outsider_athlete})
            assert resp.status_code == 404
            resp = await rider_c.post(
                "/coach-links", json={"acting_as": "athlete", "coach_user_id": outsider_user["id"]}
            )
            assert resp.status_code == 404
            # A plain athlete of the club isn't a coach to ask either, nor can they ask on someone else's behalf.
            resp = await rider_c.post("/coach-links", json={"acting_as": "athlete", "coach_user_id": rider["id"]})
            assert resp.status_code == 404
            resp = await coach_c.post(
                "/coach-links", json={"acting_as": "athlete", "athlete_id": rider_athlete, "coach_user_id": coach["id"]}
            )
            assert resp.status_code == 403
            # Riders aren't coaches: an athlete-role member can't ask to coach through the roster.
            resp = await rider_c.post("/coach-links", json={"acting_as": "coach", "athlete_id": rider_athlete})
            assert resp.status_code == 404

        # Malformed requests.
        for body in (
            {"acting_as": "coach"},
            {"acting_as": "coach", "athlete_id": rider_athlete, "athlete_email": "a@example.com"},
            {"acting_as": "athlete"},
            {"acting_as": "robot", "athlete_id": rider_athlete},
        ):
            assert (await coach_c.post("/coach-links", json=body)).status_code == 422
    finally:
        await _close(coach_c, rider_c)


async def test_asking_by_email_never_reveals_which_addresses_exist(client, db_session):
    async with _client() as coach_c, _client() as rider_c:
        await _signup(coach_c, "coach@example.com", "Coach")
        await _signup(rider_c, "rider@example.com", "Rider")

        known = await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_email": "rider@example.com"})
        unknown = await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_email": "nobody@example.com"})
        assert (known.status_code, known.json()) == (unknown.status_code, unknown.json()) == (202, {"requested": True})
        [request] = (await rider_c.get("/coach-links/inbox")).json()

        # Repeats, conflicts and self-coaching look the same too, and change nothing.
        await rider_c.post(f"/coach-links/{request['id']}/accept")
        again = await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_email": "rider@example.com"})
        myself = await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_email": "coach@example.com"})
        assert (again.status_code, again.json()) == (myself.status_code, myself.json()) == (202, {"requested": True})
        async with db_session() as session:
            assert len((await session.scalars(select(CoachAthlete))).all()) == 1

        # The athlete side works by email as well.
        await rider_c.post(f"/coach-links/{request['id']}/revoke")
        resp = await rider_c.post("/coach-links", json={"acting_as": "athlete", "coach_email": "coach@example.com"})
        assert resp.status_code == 202
        [incoming] = (await coach_c.get("/coach-links/inbox")).json()
        assert incoming["athlete_name"] == "Rider"


async def test_managed_athletes_are_answered_for_by_the_club_admin(client):
    club, admin, (coach_c, coach), (rider_c, rider), _ = await _setup(client)
    try:
        junior = (await client.post(f"/clubs/{club['id']}/athletes", json={"display_name": "Junior"})).json()

        # The admin assigns a club coach directly: active at once, no one to consent for the junior.
        resp = await client.post(
            "/coach-links", json={"acting_as": "athlete", "athlete_id": junior["id"], "coach_user_id": coach["id"]}
        )
        assert resp.status_code == 202
        assert (await coach_c.get(f"/athletes/{junior['id']}")).status_code == 200
        [theirs] = (await coach_c.get("/coach-links/athletes")).json()
        assert theirs["status"] == "active"
        assert [c["coach_name"] for c in (await client.get(f"/coach-links/coaches?athlete_id={junior['id']}")).json()] == [
            "Coach"
        ]
        # Only people who run the junior can ask on their behalf or see their coaches.
        assert (await rider_c.get(f"/coach-links/coaches?athlete_id={junior['id']}")).status_code == 403
        resp = await rider_c.post(
            "/coach-links", json={"acting_as": "athlete", "athlete_id": junior["id"], "coach_user_id": coach["id"]}
        )
        assert resp.status_code == 403

        # A managed athlete can only be given a coach of their own club.
        async with _client() as outside_coach:
            outsider = await _signup(outside_coach, "outside@example.com", "Outside")
            await _club(outside_coach, "Other")
            resp = await client.post(
                "/coach-links",
                json={"acting_as": "athlete", "athlete_id": junior["id"], "coach_user_id": outsider["id"]},
            )
            assert resp.status_code == 404  # not someone the admin shares a club with

        # A coach asking for a managed athlete waits for an admin's answer.
        second = (await client.post(f"/clubs/{club['id']}/athletes", json={"display_name": "Junior 2"})).json()
        await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_id": second["id"]})
        assert (await coach_c.get("/coach-links/inbox")).json() == []
        [pending] = (await client.get("/coach-links/inbox")).json()
        assert (pending["athlete_name"], pending["coach_name"]) == ("Junior 2", "Coach")
        assert (await coach_c.post(f"/coach-links/{pending['id']}/accept")).status_code == 403
        # A plain member of the club can't answer for the junior either.
        assert (await rider_c.post(f"/coach-links/{pending['id']}/accept")).status_code == 404
        assert (await client.post(f"/coach-links/{pending['id']}/accept")).status_code == 200
        assert (await coach_c.get(f"/athletes/{second['id']}")).status_code == 200
    finally:
        await _close(coach_c, rider_c)


async def test_deleting_a_managed_athlete_ends_their_coach_links(client, db_session):
    club, _, (coach_c, coach), (rider_c, rider), _ = await _setup(client)
    try:
        junior = (await client.post(f"/clubs/{club['id']}/athletes", json={"display_name": "Junior"})).json()
        await client.post(
            "/coach-links", json={"acting_as": "athlete", "athlete_id": junior["id"], "coach_user_id": coach["id"]}
        )
        assert (await client.delete(f"/clubs/{club['id']}/athletes/{junior['id']}")).status_code == 204
        assert (await coach_c.get("/coach-links/athletes")).json() == []
        async with db_session() as session:
            assert (await session.scalars(select(CoachAthlete))).all() == []
            assert await session.get(Athlete, uuid.UUID(junior["id"])) is None
    finally:
        await _close(coach_c, rider_c)


async def test_link_statuses_use_the_shipped_enum_values(client, db_session):
    _, _, (coach_c, coach), (rider_c, rider), rider_athlete = await _setup(client)
    try:
        await coach_c.post("/coach-links", json={"acting_as": "coach", "athlete_id": rider_athlete})
        async with db_session() as session:
            link = (await session.scalars(select(CoachAthlete))).one()
            assert link.status == CoachAthleteStatus.PENDING_ATHLETE_ACCEPTANCE
            assert str(link.initiated_by_user_id) == coach["id"] and link.responded_at is None
    finally:
        await _close(coach_c, rider_c)

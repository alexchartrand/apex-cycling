"""The club leaderboard: opt-in per athlete and club, best time per track."""

import uuid
from datetime import date

from sqlalchemy import select

from app.athletes.models import Athlete
from app.clubs.models import ClubSqorzAccount
from app.training.models import Track
from tests.test_clubs import _client, _club, _join, _signup
from tests.test_track_settings import _athlete_with_track, _track


async def _link_facility(db_session, club_id: str, track_id: str) -> None:
    async with db_session() as session:
        track = await session.get(Track, uuid.UUID(track_id))
        session.add(ClubSqorzAccount(club_id=uuid.UUID(club_id), sqorz_account_id=track.sqorz_account_id))
        await session.commit()


async def _set_profile(db_session, athlete_id: str, **fields) -> None:
    async with db_session() as session:
        athlete = await session.get(Athlete, uuid.UUID(athlete_id))
        for name, value in fields.items():
            setattr(athlete, name, value)
        await session.commit()


async def _my_athlete(client) -> str:
    return (await client.get("/athletes/me")).json()["id"]


async def _result(client, athlete_id: str, track_id: str, time_ms: int, **over) -> None:
    body = {
        "event_key": "1km",
        "start_type": "standing",
        "time_ms": time_ms,
        "achieved_on": "2026-06-01",
        "track_id": track_id,
        **over,
    }
    assert (await client.post(f"/athletes/{athlete_id}/manual-results", json=body)).status_code == 201


async def _opt_in(client, athlete_id: str, club_id: str, value: bool = True) -> dict:
    resp = await client.put(f"/athletes/{athlete_id}/clubs/{club_id}/leaderboard", json={"opt_in": value})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _board(club_id: str, track_id: str, **params) -> tuple[str, dict]:
    return f"/clubs/{club_id}/leaderboard", {"event_key": "1km", "track_id": track_id, **params}


async def _club_with_riders(client, db_session):
    """An admin (the `client`, who owns the sqorz track) and three riders in the club."""
    admin_athlete = await _athlete_with_track(client, db_session, "admin@example.com")
    track = await _track(client, admin_athlete)
    club = await _club(client)
    await _link_facility(db_session, club["id"], track["id"])
    riders = []
    for name, email in (("Ann", "ann@example.com"), ("Bob", "bob@example.com"), ("Cleo", "cleo@example.com")):
        rider = _client()
        await rider.__aenter__()
        await _signup(rider, email, name)
        await _join(rider, client, club["id"], "athlete")
        riders.append(rider)
    return club, track, riders


async def _close(riders) -> None:
    for rider in riders:
        await rider.__aexit__(None, None, None)


async def test_only_opted_in_athletes_are_ranked(client, db_session):
    club, track, riders = await _club_with_riders(client, db_session)
    try:
        ann, bob, cleo = riders
        for rider, time_ms in ((ann, 71_000), (bob, 68_500), (cleo, 66_000)):
            await _result(rider, await _my_athlete(rider), track["id"], time_ms)
        await _result(ann, await _my_athlete(ann), track["id"], 75_000)  # a slower one never replaces the best

        url, params = _board(club["id"], track["id"])
        assert (await client.get(url, params=params)).json()["entries"] == []  # nobody agreed yet
        assert (await client.get(url, params=params)).json()["participants"] == 0

        await _opt_in(ann, await _my_athlete(ann), club["id"])
        await _opt_in(bob, await _my_athlete(bob), club["id"])
        board = (await ann.get(url, params=params)).json()
        assert board["track_name"] == "Tour complet" and board["participants"] == 2
        assert [(e["rank"], e["display_name"], e["time_ms"], e["is_me"]) for e in board["entries"]] == [
            (1, "Bob", 68_500, False),
            (2, "Ann", 71_000, True),
        ]
        assert board["entries"][0]["source"] == "manual" and board["entries"][0]["achieved_on"] == "2026-06-01"
        assert "Cleo" not in str(board)  # she never opted in

        # Opting out takes the name off straight away.
        await _opt_in(bob, await _my_athlete(bob), club["id"], False)
        assert [e["display_name"] for e in (await client.get(url, params=params)).json()["entries"]] == ["Ann"]
    finally:
        await _close(riders)


async def test_equal_times_share_a_rank_and_filters_narrow_the_board(client, db_session):
    club, track, riders = await _club_with_riders(client, db_session)
    try:
        ann, bob, cleo = riders
        profiles = {
            ann: {"sex": "female", "birthdate": date(date.today().year - 17, 3, 1)},  # race age 17: U19
            bob: {"sex": "male", "birthdate": date(date.today().year - 17, 6, 1)},
            cleo: {"sex": "female", "birthdate": date(date.today().year - 33, 6, 1)},  # M30
        }
        for rider, time_ms in ((ann, 68_000), (bob, 68_000), (cleo, 70_000)):
            athlete_id = await _my_athlete(rider)
            await _result(rider, athlete_id, track["id"], time_ms)
            await _set_profile(db_session, athlete_id, **profiles[rider])
            await _opt_in(rider, athlete_id, club["id"])

        url, params = _board(club["id"], track["id"])
        board = (await client.get(url, params=params)).json()
        assert [(e["rank"], e["display_name"]) for e in board["entries"]] == [(1, "Ann"), (1, "Bob"), (3, "Cleo")]
        assert board["categories"] == ["U19", "M30"]
        assert [e["category"] for e in board["entries"]] == ["U19", "U19", "M30"]

        women = (await client.get(url, params={**params, "sex": "female"})).json()
        assert [(e["rank"], e["display_name"]) for e in women["entries"]] == [(1, "Ann"), (2, "Cleo")]
        assert women["categories"] == ["U19", "M30"]  # the filter's choices don't shrink with the filter
        youth = (await client.get(url, params={**params, "category": "U19"})).json()
        assert [e["display_name"] for e in youth["entries"]] == ["Ann", "Bob"]
        both = (await client.get(url, params={**params, "category": "U19", "sex": "male"})).json()
        assert [e["display_name"] for e in both["entries"]] == ["Bob"]
    finally:
        await _close(riders)


async def test_the_best_of_sqorz_records_and_manual_results_counts(client, db_session):
    club, track, riders = await _club_with_riders(client, db_session)
    try:
        admin_athlete = await _my_athlete(client)
        record = next(
            r for r in (await client.get(f"/athletes/{admin_athlete}/records")).json() if r["track_id"] == track["id"]
        )
        # The admin rides in the club too, and opted in.
        async with db_session() as session:
            athlete = await session.get(Athlete, uuid.UUID(admin_athlete))
            athlete.join_club(uuid.UUID(club["id"]))
            await session.commit()
        await _opt_in(client, admin_athlete, club["id"])

        url = f"/clubs/{club['id']}/leaderboard"
        params = {"event_key": record["event_key"], "start_type": record["start_type"], "track_id": track["id"]}
        board = (await client.get(url, params=params)).json()
        assert [(e["source"], e["time_ms"]) for e in board["entries"]] == [("sqorz", record["time_ms"])]

        await _result(client, admin_athlete, track["id"], record["time_ms"] - 500, event_key=record["event_key"], start_type=record["start_type"])
        board = (await client.get(url, params=params)).json()
        assert [(e["source"], e["time_ms"]) for e in board["entries"]] == [("manual", record["time_ms"] - 500)]
    finally:
        await _close(riders)


async def test_only_the_athlete_decides_to_appear(client, db_session):
    club, track, riders = await _club_with_riders(client, db_session)
    try:
        ann = riders[0]
        ann_id = await _my_athlete(ann)
        consent = f"/athletes/{ann_id}/clubs/{club['id']}/leaderboard"
        assert (await ann.get(f"/athletes/{ann_id}")).json()["leaderboard_club_ids"] == []
        assert (await _opt_in(ann, ann_id, club["id"]))["leaderboard_club_ids"] == [club["id"]]

        # The club admin sees Ann's roster entry but can't change her privacy setting.
        assert (await client.put(consent, json={"opt_in": False})).status_code == 403
        assert (await client.get(f"/athletes/{ann_id}")).json()["leaderboard_club_ids"] == [club["id"]]

        # A coach with an active link neither.
        from tests.test_activity_fusion import _coach_of

        async with _coach_of(db_session, ann_id) as coach:
            assert (await coach.put(consent, json={"opt_in": False})).status_code == 403
            assert (await coach.patch(f"/athletes/{ann_id}", json={"height_cm": 170})).status_code == 200  # the rest still works
        assert (await ann.put(consent, json={"opt_in": None})).status_code == 422
    finally:
        await _close(riders)


async def test_a_club_admin_decides_for_a_managed_athlete(client, db_session):
    await _signup(client, "boss@example.com", "Boss")
    club = await _club(client)
    managed = (await client.post(f"/clubs/{club['id']}/athletes", json={"display_name": "Junior"})).json()
    assert (await _opt_in(client, managed["id"], club["id"]))["leaderboard_club_ids"] == [club["id"]]
    assert (await _opt_in(client, managed["id"], club["id"], False))["leaderboard_club_ids"] == []


async def test_opting_in_needs_the_club(client):
    await _signup(client, "solo@example.com")
    other = (await client.post("/clubs", json={"name": "Elsewhere", "timezone": "UTC"})).json()
    # The creator is an admin there, not on its athlete roster.
    athlete_id = await _my_athlete(client)
    resp = await client.put(f"/athletes/{athlete_id}/clubs/{other['id']}/leaderboard", json={"opt_in": True})
    assert resp.status_code == 422


async def test_leaving_a_club_withdraws_the_consent_for_good(client, db_session):
    club, track, riders = await _club_with_riders(client, db_session)
    try:
        ann = riders[0]
        ann_id = await _my_athlete(ann)
        await _result(ann, ann_id, track["id"], 70_000)
        await _opt_in(ann, ann_id, club["id"])
        members = (await client.get(f"/clubs/{club['id']}/members")).json()
        membership = next(m["id"] for m in members if m["display_name"] == "Ann")

        assert (await client.delete(f"/clubs/{club['id']}/members/{membership}")).status_code == 204
        assert (await ann.get("/athletes/me")).json()["leaderboard_club_ids"] == []

        await _join(ann, client, club["id"], "athlete")  # back again
        assert (await ann.get("/athletes/me")).json()["leaderboard_club_ids"] == []
        url, params = _board(club["id"], track["id"])
        assert (await client.get(url, params=params)).json()["entries"] == []
    finally:
        await _close(riders)


async def test_consent_is_per_club(client, db_session):
    """An athlete on two rosters appears only on the board of the club she agreed to."""
    club, track, riders = await _club_with_riders(client, db_session)
    try:
        ann = riders[0]
        ann_id = await _my_athlete(ann)
        await _result(ann, ann_id, track["id"], 70_000)
        other = (await client.post("/clubs", json={"name": "Other", "timezone": "UTC"})).json()
        await _link_facility(db_session, other["id"], track["id"])
        await _join(ann, client, other["id"], "athlete")
        assert set((await ann.get("/athletes/me")).json()["club_ids"]) == {club["id"], other["id"]}

        await _opt_in(ann, ann_id, club["id"])
        url, params = _board(club["id"], track["id"])
        assert [e["display_name"] for e in (await client.get(url, params=params)).json()["entries"]] == ["Ann"]
        url, params = _board(other["id"], track["id"])
        assert (await client.get(url, params=params)).json()["entries"] == []

        # Leaving one club leaves the other roster, and its consent, alone.
        members = (await client.get(f"/clubs/{other['id']}/members")).json()
        assert (await client.delete(f"/clubs/{other['id']}/members/{next(m['id'] for m in members if m['display_name'] == 'Ann')}")).status_code == 204
        me = (await ann.get("/athletes/me")).json()
        assert (me["club_ids"], me["leaderboard_club_ids"]) == ([club["id"]], [club["id"]])
    finally:
        await _close(riders)


async def test_who_may_read_the_leaderboard(client, db_session):
    club, track, riders = await _club_with_riders(client, db_session)
    try:
        url, params = _board(club["id"], track["id"])
        async with _client() as stranger:
            await _signup(stranger, "stranger@example.com")
            assert (await stranger.get(url, params=params)).status_code == 404  # not a member
        # A track the club has no link to.
        async with db_session() as session:
            session.add(Track(sqorz_account_id="elsewhere", external_track_id="x", name="Elsewhere"))
            await session.commit()
            foreign = (await session.scalar(select(Track).where(Track.name == "Elsewhere"))).id
        assert (await client.get(url, params={**params, "track_id": str(foreign)})).status_code == 404
        assert (await client.get(url, params={**params, "event_key": "marathon"})).status_code == 422
        assert (await client.get(url, params={**params, "event_key": "f200", "start_type": "standing"})).status_code == 422
        # The start defaults to the event's first.
        flying = (await client.get(url, params={**params, "event_key": "f200"})).json()
        assert flying["start_type"] == "flying"
    finally:
        await _close(riders)

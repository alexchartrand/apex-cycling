import io
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.athletes.models import Athlete
from app.auth.models import User
from app.connections.models import DataSourceConnection, IngestionRun, IngestionRunStatus
from app.notifications import service as notification_service
from app.notifications.cli import generate_vapid
from app.notifications.kinds import DEFAULT_PREFERENCES, NotificationKind, effective_preferences
from app.notifications.messages import format_time, render
from app.notifications.models import Notification, NotificationPreference, PushSubscription
from app.notifications.producers import notify_new_records, notify_sync_failed
from app.notifications.push import PushResult
from tests.test_clubs import PASSWORD, _client, _signup
from tests.test_comments import _make_pair, _post
from tests.test_planning import _plan
from tests.test_records import _athlete_with_fixture


@pytest.fixture
async def pair(client, db_session):
    """`client` is the athlete; yields (coach client, coach user, athlete id).
    Linking them already notified the coach; that is settled here (read and
    delivered) so each test starts from an empty bell and outbox.
    """
    coach_c, coach, athlete_id = await _make_pair(client, db_session)
    assert (await coach_c.post("/notifications/read", json={})).status_code == 204
    async with db_session() as session:
        await session.execute(update(Notification).values(delivered_at=datetime.now(timezone.utc)))
        await session.commit()
    yield coach_c, coach, athlete_id
    await coach_c.aclose()


async def _of(client, kind: str) -> list[dict]:
    return [n for n in (await client.get("/notifications")).json() if n["kind"] == kind]


async def _rows(db_session, **filters) -> list[Notification]:
    async with db_session() as session:
        return list((await session.scalars(select(Notification).filter_by(**filters).order_by(Notification.created_at))).all())


# --- preferences -------------------------------------------------------------


def test_defaults_are_all_on_except_email_for_records():
    assert set(DEFAULT_PREFERENCES) == {kind.value for kind in NotificationKind}
    assert DEFAULT_PREFERENCES["new_pr"] == {"in_app": True, "push": True, "email": False}
    assert DEFAULT_PREFERENCES["comment"] == {"in_app": True, "push": True, "email": True}


def test_stored_overrides_are_applied_and_junk_is_ignored():
    merged = effective_preferences(
        {"comment": {"email": False, "bogus": True, "push": "yes"}, "unknown_kind": {"email": False}, "new_pr": "x"}
    )
    assert merged["comment"] == {"in_app": True, "push": True, "email": False}
    assert merged["new_pr"] == DEFAULT_PREFERENCES["new_pr"]
    assert "unknown_kind" not in merged
    assert DEFAULT_PREFERENCES["comment"]["email"] is True  # the defaults aren't mutated


# --- the bell ------------------------------------------------------------------


async def test_a_comment_notifies_the_other_side_and_not_its_author(client, pair):
    coach_c, _coach, athlete_id = pair
    await _post(client, athlete_id, "Legs felt heavy today")

    assert (await client.get("/notifications")).json() == []  # the author hears nothing
    assert (await coach_c.get("/notifications/unread-count")).json() == {"count": 1}
    [note] = await _of(coach_c, "comment")
    assert note["read_at"] is None
    assert note["payload"]["author_name"] == "Rider"
    assert note["payload"]["athlete_id"] == athlete_id
    assert note["payload"]["external_event_id"] == "evt-1"
    assert note["payload"]["session_name"] == "Morning ride"
    assert note["payload"]["excerpt"] == "Legs felt heavy today"

    await _post(coach_c, athlete_id, "Keep the next one easy.")
    [reply] = await _of(client, "comment")
    assert reply["payload"]["author_name"] == "Coach"
    # The coach is in the thread, so a second message from the athlete reaches them too.
    await _post(client, athlete_id, "Will do")
    assert (await coach_c.get("/notifications/unread-count")).json() == {"count": 2}


async def test_marking_read_one_or_all_and_only_your_own(client, pair):
    coach_c, _coach, athlete_id = pair
    for text in ("one", "two", "three"):
        await _post(client, athlete_id, text)
    ids = [n["id"] for n in await _of(coach_c, "comment")]
    assert len(ids) == 3

    # Someone else's id does nothing.
    assert (await client.post("/notifications/read", json={"ids": ids})).status_code == 204
    assert (await coach_c.get("/notifications/unread-count")).json() == {"count": 3}

    assert (await coach_c.post("/notifications/read", json={"ids": ids[:1]})).status_code == 204
    assert (await coach_c.get("/notifications/unread-count")).json() == {"count": 2}
    assert (await coach_c.post("/notifications/read", json={})).status_code == 204
    assert (await coach_c.get("/notifications/unread-count")).json() == {"count": 0}
    assert all(n["read_at"] for n in (await coach_c.get("/notifications")).json())


async def test_notifications_need_a_login(client):
    for path in ("/notifications", "/notifications/unread-count", "/notifications/preferences", "/notifications/push"):
        assert (await client.get(path)).status_code == 401


async def test_a_coaching_request_notifies_the_side_that_must_answer(client, db_session):
    await _signup(client, "rider@example.com", "Rider")
    coach_c = _client()
    coach = await _signup(coach_c, "coach@example.com", "Coach")

    await client.post("/coach-links", json={"acting_as": "athlete", "coach_email": coach["email"]})
    [note] = (await coach_c.get("/notifications")).json()
    assert note["kind"] == "coach_request"
    assert note["payload"]["from_name"] == "Rider" and note["payload"]["asked_role"] == "athlete"

    # Asking again changes nothing, so nobody is pinged twice.
    await client.post("/coach-links", json={"acting_as": "athlete", "coach_email": coach["email"]})
    assert len((await coach_c.get("/notifications")).json()) == 1

    # The coach asking the athlete (a new link, other direction) notifies the athlete.
    other = _client()
    other_coach = await _signup(other, "coach2@example.com", "Second Coach")
    resp = await other.post("/coach-links", json={"acting_as": "coach", "athlete_email": "rider@example.com"})
    assert resp.status_code == 202, resp.text
    [asked] = (await client.get("/notifications")).json()
    assert asked["payload"]["from_name"] == "Second Coach" and asked["payload"]["asked_role"] == "coach"
    assert other_coach["email"] != coach["email"]
    await coach_c.aclose()
    await other.aclose()


async def test_a_plan_from_the_coach_notifies_the_athlete_but_not_their_own(client, pair):
    coach_c, _coach, athlete_id = pair
    url = f"/athletes/{athlete_id}/planned-sessions"

    assert (await client.post(url, json=_plan())).status_code == 201
    assert await _of(client, "plan_added") == []

    assert (await coach_c.post(url, json=_plan(title="Flying 200s"))).status_code == 201
    [note] = await _of(client, "plan_added")
    assert note["payload"]["title"] == "Flying 200s" and note["payload"]["author_name"] == "Coach"
    assert await _of(coach_c, "plan_added") == []


# --- preferences through the API ---------------------------------------------------


async def test_preferences_default_then_change_what_is_recorded(client, db_session, pair):
    coach_c, _coach, athlete_id = pair
    prefs = (await coach_c.get("/notifications/preferences")).json()
    assert prefs["kinds"]["new_pr"] == {"in_app": True, "push": True, "email": False}
    assert prefs["email_available"] is False and prefs["push_available"] is False  # nothing configured in tests

    # Everything off for comments: nothing is recorded at all.
    off = {"in_app": False, "push": False, "email": False}
    resp = await coach_c.put("/notifications/preferences", json={"kinds": {"comment": off}})
    assert resp.status_code == 200 and resp.json()["kinds"]["comment"] == off
    assert resp.json()["kinds"]["plan_added"]["in_app"] is True  # other kinds untouched
    await _post(client, athlete_id, "hello")
    assert await _of(coach_c, "comment") == []

    # Bell off but email on: recorded for delivery, hidden from the bell.
    mail_only = {"in_app": False, "push": False, "email": True}
    await coach_c.put("/notifications/preferences", json={"kinds": {"comment": mail_only}})
    await _post(client, athlete_id, "again")
    assert await _of(coach_c, "comment") == []
    assert (await coach_c.get("/notifications/unread-count")).json() == {"count": 0}
    [row] = await _rows(db_session, kind="comment")
    assert (row.in_app, row.want_push, row.want_email, row.delivered_at) == (False, False, True, None)


async def test_a_notification_with_nothing_to_send_is_complete_at_once(client, db_session, pair):
    _coach_c, _coach, athlete_id = pair
    await _post(client, athlete_id, "hello")  # the coach: bell on, push on, email on
    # The athlete mutes email and push for plans: only the bell remains.
    await client.put(
        "/notifications/preferences", json={"kinds": {"plan_added": {"in_app": True, "push": False, "email": False}}}
    )
    coach_c = pair[0]
    await coach_c.post(f"/athletes/{athlete_id}/planned-sessions", json=_plan())
    [plan_note] = await _rows(db_session, kind="plan_added")
    assert plan_note.delivered_at is not None and not plan_note.want_push and not plan_note.want_email
    [comment_note] = await _rows(db_session, kind="comment")
    assert comment_note.delivered_at is None and comment_note.want_push and comment_note.want_email


# --- push subscriptions ------------------------------------------------------------


async def test_push_config_is_off_without_vapid_keys_and_on_with_them(client, monkeypatch):
    await _signup(client, "pusher@example.com")
    assert (await client.get("/notifications/push")).json() == {"enabled": False, "public_key": None}

    from app.core import config

    monkeypatch.setattr(config.get_settings(), "vapid_public_key", "PUBLIC")
    monkeypatch.setattr(config.get_settings(), "vapid_private_key", "PRIVATE")
    assert (await client.get("/notifications/push")).json() == {"enabled": True, "public_key": "PUBLIC"}


async def test_subscribing_is_idempotent_moves_with_the_browser_and_unsubscribes(client, db_session):
    first = await _signup(client, "one@example.com")
    body = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k1", "auth": "a1"}}
    assert (await client.post("/notifications/push/subscriptions", json=body)).status_code == 204
    assert (await client.post("/notifications/push/subscriptions", json=body)).status_code == 204

    async with db_session() as session:
        [row] = (await session.scalars(select(PushSubscription))).all()
        assert row.user_id == uuid.UUID(first["id"])

    # The same browser signs in as someone else: the subscription follows.
    async with _client() as other:
        second = await _signup(other, "two@example.com")
        assert (await other.post("/notifications/push/subscriptions", json={**body, "keys": {"p256dh": "k2", "auth": "a2"}})).status_code == 204
        async with db_session() as session:
            [row] = (await session.scalars(select(PushSubscription))).all()
            assert (row.user_id, row.p256dh) == (uuid.UUID(second["id"]), "k2")
        # Someone else can't remove it...
        await client.post("/notifications/push/unsubscribe", json={"endpoint": body["endpoint"]})
        async with db_session() as session:
            assert len((await session.scalars(select(PushSubscription))).all()) == 1
        # ...but its owner can.
        await other.post("/notifications/push/unsubscribe", json={"endpoint": body["endpoint"]})
        async with db_session() as session:
            assert (await session.scalars(select(PushSubscription))).all() == []

    assert (await client.post("/notifications/push/subscriptions", json={"endpoint": "", "keys": {"p256dh": "k", "auth": "a"}})).status_code == 422


# --- delivery ------------------------------------------------------------------------


class _Outbox:
    def __init__(self):
        self.pushes: list[tuple[str, dict]] = []
        self.emails: list[tuple[str, str, str]] = []
        self.gone: set[str] = set()


@pytest.fixture
def outbox(monkeypatch):
    box = _Outbox()

    async def fake_push(target, data):
        box.pushes.append((target.endpoint, data))
        return PushResult.GONE if target.endpoint in box.gone else PushResult.SENT

    async def fake_email(to, subject, body):
        box.emails.append((to, subject, body))
        return True

    monkeypatch.setattr(notification_service, "push_enabled", lambda: True)
    monkeypatch.setattr(notification_service, "mail_enabled", lambda: True)
    monkeypatch.setattr(notification_service, "send_push", fake_push)
    monkeypatch.setattr(notification_service, "send_email", fake_email)
    return box


async def test_delivery_pushes_to_every_browser_emails_in_the_users_language_and_forgets_dead_devices(
    client, db_session, pair, outbox
):
    coach_c, coach, athlete_id = pair
    for n, endpoint in enumerate(("https://push.example/a", "https://push.example/dead")):
        await coach_c.post(
            "/notifications/push/subscriptions", json={"endpoint": endpoint, "keys": {"p256dh": f"k{n}", "auth": f"a{n}"}}
        )
    outbox.gone.add("https://push.example/dead")
    async with db_session() as session:
        (await session.get(User, uuid.UUID(coach["id"]))).locale = "en"
        await session.commit()

    await _post(client, athlete_id, "Legs felt heavy today")
    async with db_session() as session:
        assert await notification_service.deliver_pending(session) == 1

    assert sorted(endpoint for endpoint, _ in outbox.pushes) == ["https://push.example/a", "https://push.example/dead"]
    _, data = outbox.pushes[0]
    assert data["title"] == "New comment from Rider"
    assert data["body"] == "Morning ride: Legs felt heavy today"
    assert data["url"] == "/sessions/evt-1?tab=comments"
    [(to, subject, body)] = outbox.emails
    assert to == "coach@example.com" and subject == "New comment from Rider"
    assert "/sessions/evt-1?tab=comments" in body and body.count("http") == 1

    async with db_session() as session:
        assert [s.endpoint for s in (await session.scalars(select(PushSubscription))).all()] == ["https://push.example/a"]
        [row] = (await session.scalars(select(Notification).where(Notification.kind == "comment"))).all()
        assert row.delivered_at is not None
        # Nothing is sent twice.
        assert await notification_service.deliver_pending(session) == 0
    assert len(outbox.emails) == 1


async def test_delivery_without_a_locale_is_french_and_skips_what_is_not_configured(client, db_session, pair, monkeypatch):
    _coach_c, _coach, athlete_id = pair
    sent: list = []

    async def fake_email(to, subject, body):
        sent.append(subject)

    monkeypatch.setattr(notification_service, "send_email", fake_email)  # mail_enabled() is False: not called
    await _post(client, athlete_id, "hello")
    async with db_session() as session:
        assert await notification_service.deliver_pending(session) == 1
        [row] = (await session.scalars(select(Notification).where(Notification.kind == "comment"))).all()
        assert row.delivered_at is not None  # processed, though nothing could be sent
    assert sent == []

    assert render("comment", {"author_name": "Rider", "session_name": "S", "excerpt": "x"}, None).title == "Nouveau commentaire de Rider"
    assert render("comment", {"author_name": "Rider", "session_name": "S", "excerpt": "x"}, "de").title == "Nouveau commentaire de Rider"


def test_message_texts_for_every_kind_and_language():
    pr = {
        "external_event_id": "e1",
        "session_name": "Kilo day",
        "count": 1,
        "items": [{"event_key": "500m", "start_type": "standing", "time_ms": 47_535}],
    }
    en = render("new_pr", pr, "en")
    assert (en.title, en.body, en.url) == ("New record: 500 m", "Kilo day: 500 m in 47.535 s", "/sessions/e1")
    assert render("new_pr", {**pr, "count": 3}, "en").title == "3 new records"
    assert render("new_pr", {**pr, "items": [{"event_key": "2km", "time_ms": 150_000}]}, "fr").title == "Nouveau record : poursuite 2 km"
    assert render("sync_failed", {"transponder_code": "LS-1", "error": "boom"}, "en").url == "/import"
    ask = render("coach_request", {"from_name": "Ann", "asked_role": "athlete"}, "en")
    assert ask.body == "Ann would like you to coach them." and ask.url == "/coach"
    assert render("coach_request", {"from_name": "Ann", "asked_role": "coach"}, "en").body == "Ann would like to coach you."
    assert "Ann planned" in render("plan_added", {"author_name": "Ann", "title": "T", "planned_date": "2026-01-02"}, "en").body
    assert format_time(72_345) == "1:12.345" and format_time(9_999) == "9.999 s"


# --- sync failures and records --------------------------------------------------------


async def _run(db_session, connection_id, status, minutes_ago) -> uuid.UUID:
    async with db_session() as session:
        run = IngestionRun(
            data_source_connection_id=connection_id,
            requested_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            status=status,
        )
        session.add(run)
        await session.commit()
        return run.id


async def test_a_failed_sync_notifies_the_transponders_user_once_per_streak(client, db_session):
    await _athlete_with_fixture(client, db_session, "streak@example.com")
    async with db_session() as session:
        connection_id = (await session.scalar(select(DataSourceConnection.id).where(DataSourceConnection.external_id == "LS-03407")))

    async def fail(minutes_ago) -> None:
        run_id = await _run(db_session, connection_id, IngestionRunStatus.FAILED, minutes_ago)
        async with db_session() as session:
            await notify_sync_failed(session, connection_id, run_id, "HTTP 503 " + "x" * 400)
            await session.commit()

    await fail(60)
    [note] = (await client.get("/notifications")).json()
    assert note["kind"] == "sync_failed" and note["payload"]["transponder_code"] == "LS-03407"
    assert len(note["payload"]["error"]) == 200

    await fail(40)  # still failing: nothing new
    assert len((await client.get("/notifications")).json()) == 1

    await _run(db_session, connection_id, IngestionRunStatus.SUCCESS, 20)
    await fail(5)  # failing again after a success: a new streak
    assert len((await client.get("/notifications")).json()) == 2


async def test_new_records_are_announced_once_per_session_within_the_window(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "records-news@example.com")

    async def announce(today) -> None:
        async with db_session() as session:
            await notify_new_records(session, [athlete_id], today=today)
            await session.commit()

    await announce(date(2026, 10, 23))  # the fixture's sessions are months old
    assert (await client.get("/notifications")).json() == []

    await announce(date(2026, 4, 6))
    [note] = (await client.get("/notifications")).json()
    assert note["kind"] == "new_pr"
    assert note["payload"]["count"] == 6 and len(note["payload"]["items"]) == 5  # capped for display
    assert len(note["payload"]["insight_keys"]) == 6
    assert note["payload"]["session_name"] and note["payload"]["external_event_id"]
    assert {"event_key", "time_ms", "previous_ms", "track_name"} <= set(note["payload"]["items"][0])

    await announce(date(2026, 4, 6))  # a later sync with nothing new says nothing
    assert len((await client.get("/notifications")).json()) == 1


async def test_a_managed_athlete_has_nobody_to_notify(client, db_session):
    athlete_id = await _athlete_with_fixture(client, db_session, "managed@example.com")
    async with db_session() as session:
        athlete = await session.get(Athlete, athlete_id)
        athlete.user_id = None
        await session.commit()
    async with db_session() as session:
        await notify_new_records(session, [athlete_id], today=date(2026, 4, 6))
        await session.commit()
    assert await _rows(db_session) == []


# --- account ---------------------------------------------------------------------------


async def test_export_and_account_deletion_cover_notifications(client, db_session, pair):
    coach_c, coach, athlete_id = pair
    await _post(client, athlete_id, "hello")
    await coach_c.put("/notifications/preferences", json={"kinds": {"new_pr": {"in_app": False, "push": False, "email": True}}})
    await coach_c.post("/notifications/push/subscriptions", json={"endpoint": "https://push.example/c", "keys": {"p256dh": "k", "auth": "a"}})

    export = await coach_c.get("/auth/me/export")
    assert export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        assert "comment" in archive.read("notifications.csv").decode()
        assert '"new_pr"' in archive.read("notification_preferences.json").decode()

    resp = await coach_c.post("/auth/delete-account", json={"password": PASSWORD})
    assert resp.status_code in (200, 204), resp.text
    async with db_session() as session:
        for model in (Notification, NotificationPreference, PushSubscription):
            assert (await session.scalars(select(model).where(model.user_id == uuid.UUID(coach["id"])))).all() == []


# --- operator tooling ---------------------------------------------------------------------


def test_generated_vapid_keys_have_the_shape_browsers_expect():
    import base64

    public, private = generate_vapid()
    pad = lambda value: value + "=" * (-len(value) % 4)  # noqa: E731
    assert len(base64.urlsafe_b64decode(pad(public))) == 65 and base64.urlsafe_b64decode(pad(public))[0] == 4
    assert len(base64.urlsafe_b64decode(pad(private))) == 32
    assert generate_vapid() != (public, private)

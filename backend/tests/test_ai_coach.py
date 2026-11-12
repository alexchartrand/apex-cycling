"""The AI coach: access and consent, the conversation loop with tools, the
proposal → accept path, reports and replans — all with a scripted model."""

import io
import json
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, update

from app.activities.models import Activity, ActivitySource
from app.athletes.models import Athlete, AthleteMetric, CoachAthlete, CoachAthleteStatus
from app.auth.models import User
from app.coach_ai import reports as report_service
from app.coach_ai.context import build_brief
from app.coach_ai.models import (
    AiCoachAccess,
    AiConversation,
    AiMessage,
    AiProposal,
    AiReport,
    AiUsage,
    ProposalStatus,
)
from app.coach_ai.ports import LlmError, LlmReply, ToolCall
from app.coach_ai.router import get_llm_client
from app.core.config import get_settings
from app.main import app
from app.notifications.models import Notification
from app.planning.models import PlannedSession
from app.workouts.models import Workout
from tests.test_account import _other_client, _rows_referencing, _signup


class FakeLlm:
    """Replies from a script; each entry is an `LlmReply` or a function of
    (messages, tools) returning one. Records what it was sent."""

    model = "fake-large"

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[dict] = []

    async def chat(self, messages, *, tools=None, json_mode=False, temperature=0.4, max_tokens=None):
        self.calls.append({"messages": messages, "tools": tools})
        if not self.script:
            raise AssertionError("the model was called more often than scripted")
        step = self.script.pop(0)
        reply = step(messages, tools) if callable(step) else step
        if isinstance(reply, Exception):
            raise reply
        return reply


def say(text: str, tokens: int = 100) -> LlmReply:
    return LlmReply(content=text, prompt_tokens=tokens, completion_tokens=tokens // 2, model="fake-large")


def call(name: str, args: dict, call_id: str = "c1") -> LlmReply:
    return LlmReply(
        content="", tool_calls=[ToolCall(id=call_id, name=name, arguments=json.dumps(args))], prompt_tokens=50, model="fake-large"
    )


def _workout(minutes: int = 60) -> dict:
    return {
        "name": "Endurance",
        "steps": [
            {"kind": "warmup", "duration_s": 600, "power": {"unit": "ftp_pct", "low": 50, "high": 65}},
            {"kind": "work", "duration_s": (minutes - 15) * 60, "power": {"unit": "ftp_pct", "low": 65, "high": 75}},
            {"kind": "cooldown", "duration_s": 300, "power": {"unit": "ftp_pct", "low": 50}},
        ],
    }


@pytest.fixture
def mistral_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "mistral_api_key", "test-key")


@pytest.fixture
def llm():
    fake = FakeLlm()
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm_client, None)


async def _athlete(client) -> str:
    await _signup(client, "rider@example.com")
    return (await client.get("/athletes/me")).json()["id"]


async def _enable(db_session, athlete_id: str, *, consent: bool = True, cap: int | None = None) -> None:
    async with db_session() as session:
        session.add(
            AiCoachAccess(
                athlete_id=uuid.UUID(athlete_id),
                enabled=True,
                approved_at=datetime.now(timezone.utc) - timedelta(days=30),
                consent_at=datetime.now(timezone.utc) if consent else None,
                monthly_token_cap=cap,
            )
        )
        session.add(AthleteMetric(athlete_id=uuid.UUID(athlete_id), effective_date=date(2026, 1, 1), ftp_w=250, weight_kg=72))
        await session.commit()


async def _ready(client, db_session) -> str:
    athlete_id = await _athlete(client)
    await _enable(db_session, athlete_id)
    return athlete_id


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# --- access ----------------------------------------------------------------------------


async def test_off_without_a_key_and_until_an_admin_enables_it(client, db_session, monkeypatch):
    athlete_id = await _athlete(client)
    base = f"/athletes/{athlete_id}/ai-coach"
    status = (await client.get(base)).json()
    assert status["available"] is False and status["enabled"] is False and status["can_use"] is False
    assert (await client.post(f"{base}/consent")).status_code == 503

    monkeypatch.setattr(get_settings(), "mistral_api_key", "test-key")
    refused = await client.post(f"{base}/consent")
    assert refused.status_code == 403 and refused.json()["detail"] == "ai_coach_not_enabled"
    assert (await client.get(f"{base}/admin")).status_code in (404, 405)

    # A platform admin turns it on.
    async with _other_client() as admin:
        admin_user = await _signup(admin, "admin@example.com")
        assert (await admin.put(f"/admin/ai-coach/{athlete_id}", json={"enabled": True})).status_code == 403
        async with db_session() as session:
            await session.execute(update(User).where(User.id == uuid.UUID(admin_user["id"])).values(is_platform_admin=True))
            await session.commit()
        listed = (await admin.get("/admin/ai-coach", params={"q": "rider@"})).json()
        assert [r["email"] for r in listed["rows"]] == ["rider@example.com"] and listed["rows"][0]["enabled"] is False
        row = (await admin.put(f"/admin/ai-coach/{athlete_id}", json={"enabled": True, "monthly_token_cap": 5000})).json()
        assert row["enabled"] is True and row["monthly_token_cap"] == 5000
        # Without a search, the list is the athletes who have access.
        assert [r["athlete_id"] for r in (await admin.get("/admin/ai-coach")).json()["rows"]] == [athlete_id]

    status = (await client.get(base)).json()
    assert status["enabled"] is True and status["consented"] is False and status["can_use"] is False
    no_consent = await client.get(f"{base}/conversations")
    assert no_consent.status_code == 403 and no_consent.json()["detail"] == "ai_coach_no_consent"

    status = (await client.post(f"{base}/consent")).json()
    assert status["can_use"] is True and status["usage"] == {"month_tokens": 0, "monthly_cap": 5000}
    assert (await client.get(f"{base}/conversations")).json() == []

    withdrawn = (await client.post(f"{base}/consent/withdraw", json={"delete_history": True})).json()
    assert withdrawn["consented"] is False and withdrawn["can_use"] is False


async def test_only_the_athlete_themself_talks_to_it(client, db_session, mistral_on):
    athlete_id = await _ready(client, db_session)
    base = f"/athletes/{athlete_id}/ai-coach"
    async with _other_client() as coach:
        coach_user = await _signup(coach, "coach@example.com")
        async with db_session() as session:
            session.add(
                CoachAthlete(
                    coach_user_id=uuid.UUID(coach_user["id"]), athlete_id=uuid.UUID(athlete_id), status=CoachAthleteStatus.ACTIVE
                )
            )
            await session.commit()
        assert (await coach.get(base)).json()["is_self"] is False
        assert (await coach.get(f"{base}/conversations")).status_code == 403
        assert (await coach.post(f"{base}/conversations", json={"content": "hi"})).status_code == 403
        # The coach reads the reports and proposals.
        assert (await coach.get(f"{base}/reports")).status_code == 200
        assert (await coach.get(f"{base}/proposals")).status_code == 200


async def test_a_managed_athlete_cant_be_enabled(client, db_session, monkeypatch):
    async with db_session() as session:
        managed = Athlete(display_name="Junior")
        admin = User(email="root@example.com", hashed_password="x", is_platform_admin=True)
        session.add_all([managed, admin])
        await session.commit()
        managed_id = managed.id
    await _signup(client, "root2@example.com")
    async with db_session() as session:
        await session.execute(update(User).where(User.email == "root2@example.com").values(is_platform_admin=True))
        await session.commit()
    assert (await client.put(f"/admin/ai-coach/{managed_id}", json={"enabled": True})).status_code == 422


# --- conversations ----------------------------------------------------------------------


async def test_a_chat_turn_uses_tools_and_keeps_them_out_of_sight(client, db_session, mistral_on, llm):
    athlete_id = await _ready(client, db_session)
    base = f"/athletes/{athlete_id}/ai-coach"
    llm.script = [
        call("get_plans", {"start": _future(0), "end": _future(7)}),
        say("Nothing planned this week. **Rest**, then we build."),
    ]
    turn = await client.post(f"{base}/conversations", json={"content": "What's on this week?"})
    assert turn.status_code == 201, turn.text
    body = turn.json()
    assert [(m["role"], m["content"]) for m in body["messages"]] == [
        ("user", "What's on this week?"),
        ("assistant", "Nothing planned this week. **Rest**, then we build."),
    ]
    # The model got the brief, then the tool result.
    first = llm.calls[0]["messages"]
    assert first[0]["role"] == "system" and '"ftp_w":250' in first[0]["content"]
    assert {t["function"]["name"] for t in llm.calls[0]["tools"]} >= {"get_plans", "propose_changes", "save_profile"}
    second = llm.calls[1]["messages"]
    assert second[-1]["role"] == "tool" and second[-1]["content"] == "[]"

    conversation_id = body["conversation_id"]
    shown = (await client.get(f"{base}/conversations/{conversation_id}")).json()
    assert [m["role"] for m in shown["messages"]] == ["user", "assistant"]
    assert shown["title"] == "What's on this week?"

    llm.script = [say("Sure.")]
    follow = await client.post(f"{base}/conversations/{conversation_id}/messages", json={"content": "Thanks"})
    assert [m["content"] for m in follow.json()["messages"]] == ["Thanks", "Sure."]
    # Earlier turns go back to the model, tool traffic included.
    assert [m["role"] for m in llm.calls[-1]["messages"]] == ["system", "user", "assistant", "tool", "assistant", "user"]

    usage = (await client.get(base)).json()["usage"]
    assert usage["month_tokens"] == 50 + 150 + 150


async def test_a_failed_model_call_keeps_nothing_but_the_tokens(client, db_session, mistral_on, llm):
    athlete_id = await _ready(client, db_session)
    llm.script = [call("get_training_load", {"weeks": 4}), LlmError("down")]
    failed = await client.post(f"/athletes/{athlete_id}/ai-coach/conversations", json={"content": "hello"})
    assert failed.status_code == 502 and failed.json()["detail"] == "ai_coach_failed"
    async with db_session() as session:
        assert (await session.scalars(select(AiConversation))).all() == []
        assert [u.prompt_tokens for u in (await session.scalars(select(AiUsage))).all()] == [50]


async def test_over_the_cap_the_model_isnt_called(client, db_session, mistral_on, llm):
    athlete_id = await _athlete(client)
    await _enable(db_session, athlete_id, cap=100)
    async with db_session() as session:
        session.add(AiUsage(athlete_id=uuid.UUID(athlete_id), model="m", purpose="chat", prompt_tokens=90, completion_tokens=20))
        await session.commit()
    refused = await client.post(f"/athletes/{athlete_id}/ai-coach/conversations", json={"content": "hello"})
    assert refused.status_code == 429 and refused.json()["detail"] == "ai_coach_cap_reached"
    assert llm.calls == []


async def test_the_brief_never_contains_strava_data(client, db_session, mistral_on):
    athlete_id = await _ready(client, db_session)
    async with db_session() as session:
        start = datetime.now(timezone.utc) - timedelta(days=2)
        for source, name in ((ActivitySource.STRAVA, "Strava ride"), (ActivitySource.UPLOAD, "My own file")):
            session.add(
                Activity(athlete_id=uuid.UUID(athlete_id), source=source, name=name, start_time=start, elapsed_s=3600, tss=60)
            )
        await session.commit()
        athlete = await session.get(Athlete, uuid.UUID(athlete_id))
        brief = await build_brief(session, athlete, locale="en")
    names = [t.get("name") for t in brief["recent_training"]]
    assert names == ["My own file"]
    assert "Strava ride" not in json.dumps(brief)
    # The load the AI sees doesn't count the Strava ride either.
    assert sum(w["tss"] for w in brief["load"]["weekly_tss"]) == 60


# --- proposals ------------------------------------------------------------------------------


async def test_intake_saves_answers_proposes_a_plan_and_accepting_writes_the_calendar(client, db_session, mistral_on, llm):
    athlete_id = await _ready(client, db_session)
    base = f"/athletes/{athlete_id}/ai-coach"
    llm.script = [say("Hi! How many hours a week can you train, and on which days?")]
    started = await client.post(f"{base}/conversations", json={"kind": "intake"})
    assert started.status_code == 201
    conversation_id = started.json()["conversation_id"]
    # The kick-off is hidden: the conversation opens on the coach's questions.
    assert [m["role"] for m in started.json()["messages"]] == ["assistant"]
    assert "Task: build a training program" in llm.calls[0]["messages"][0]["content"]

    ops = [
        {"op": "create", "date": _future(1), "title": "Endurance", "workout": {**_workout(60), "save_to_library": True}},
        {"op": "create", "date": _future(3), "title": "Gym", "workout": {
            "name": "Strength A",
            "steps": [{"kind": "work", "label": "Back squat", "notes": "4×5 @ 80 %", "rpe": 8, "duration_s": 900}],
        }},
    ]
    llm.script = [
        call("save_profile", {"fields": {"hours_per_week": 6, "available_days": [2, 4, 6], "injuries": "none", "gym": True}}),
        call("propose_changes", {"summary": "Base block", "ops": [{"op": "create", "date": "2020-01-01", "title": "x", "workout_id": str(uuid.uuid4())}]}, "c2"),
        call("propose_changes", {"summary": "Two base weeks, then build.", "goal": "Sub 1:10 kilo", "ops": ops,
                                 "outline": [{"week_start": _future(14), "focus": "Build", "hours": 7}]}, "c3"),
        say("Here is your program. It waits for your OK."),
    ]
    turn = await client.post(f"{base}/conversations/{conversation_id}/messages", json={"content": "6 h, Tue Thu Sat, no injuries, gym yes"})
    assert turn.status_code == 200, turn.text
    # The first proposal's errors went back to the model.
    errors = json.loads(llm.calls[3]["messages"][-1]["content"])
    assert errors["ok"] is False and any("in the past" in e for e in errors["errors"])
    assert any("no workout" in e for e in errors["errors"])

    answer = turn.json()["messages"][-1]
    proposal = answer["proposal"]
    assert answer["content"] == "Here is your program. It waits for your OK."
    assert proposal["kind"] == "plan" and proposal["status"] == "pending" and proposal["can_decide"]
    assert [i["op"] for i in proposal["items"]] == ["create", "create"]
    assert proposal["items"][0]["estimate"]["duration_s"] == 3600
    assert proposal["goal"] == "Sub 1:10 kilo" and proposal["outline"][0]["focus"] == "Build"
    profile = (await client.get(f"{base}/profile")).json()
    assert profile["answers"]["hours_per_week"] == 6 and profile["answers"]["available_days"] == [2, 4, 6]
    # Nothing on the calendar yet.
    assert (await client.get(f"/athletes/{athlete_id}/planned-sessions")).json() == []

    accepted = await client.post(f"{base}/proposals/{proposal['id']}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    plans = (await client.get(f"/athletes/{athlete_id}/planned-sessions")).json()
    assert [(p["title"], p["created_by_ai"]) for p in plans] == [("Endurance", True), ("Gym", True)]
    assert plans[0]["workout_estimate"]["tss"] > 0 and plans[1]["workout"][0]["label"] == "Back squat"
    async with db_session() as session:
        library = (await session.scalars(select(Workout))).all()
        assert [(w.name, w.tags, w.created_by_ai) for w in library] == [("Endurance", ["ai"], True)]
    assert (await client.get(f"{base}/profile")).json()["program"]["goal"] == "Sub 1:10 kilo"
    assert (await client.post(f"{base}/proposals/{proposal['id']}/accept")).status_code == 409


async def test_chat_changes_never_touch_the_coachs_plans(client, db_session, mistral_on, llm):
    athlete_id = await _ready(client, db_session)
    base = f"/athletes/{athlete_id}/ai-coach"
    plans_url = f"/athletes/{athlete_id}/planned-sessions"
    mine = (await client.post(plans_url, json={"planned_date": _future(2), "title": "My ride", "workout": _workout()["steps"]})).json()
    async with _other_client() as coach:
        coach_user = await _signup(coach, "coach@example.com")
        async with db_session() as session:
            session.add(
                CoachAthlete(
                    coach_user_id=uuid.UUID(coach_user["id"]), athlete_id=uuid.UUID(athlete_id), status=CoachAthleteStatus.ACTIVE
                )
            )
            await session.commit()
        theirs = (await coach.post(plans_url, json={"planned_date": _future(3), "title": "Coach's kilos", "workout": _workout()["steps"]})).json()

        llm.script = [
            call("propose_changes", {"summary": "s", "ops": [{"op": "skip", "plan_id": theirs["id"]}]}),
            call("propose_changes", {"summary": "Moved to Friday.", "ops": [{"op": "update", "plan_id": mine["id"], "date": _future(4)}]}, "c2"),
            say("Moved it."),
        ]
        turn = (await client.post(f"{base}/conversations", json={"content": "Move my ride"})).json()
        refused = json.loads(llm.calls[1]["messages"][-1]["content"])
        assert refused["ok"] is False and "planned by the coach" in refused["errors"][0]
        proposal = turn["messages"][-1]["proposal"]
        assert proposal["items"][0]["before"]["planned_date"] == mine["planned_date"]
        assert proposal["items"][0]["planned_date"] == _future(4)

        # The coach reads the proposal but can't decide it.
        seen = (await coach.get(f"{base}/proposals/{proposal['id']}")).json()
        assert seen["can_decide"] is False
        assert (await coach.post(f"{base}/proposals/{proposal['id']}/accept")).status_code == 403

        assert (await client.post(f"{base}/proposals/{proposal['id']}/accept")).status_code == 200
        moved = (await client.get(f"{plans_url}")).json()
        assert {p["title"]: p["planned_date"] for p in moved} == {"My ride": _future(4), "Coach's kilos": _future(3)}

        # An AI plan stays editable by the coach.
        llm.script = [
            call("propose_changes", {"summary": "Add one.", "ops": [{"op": "create", "date": _future(5), "title": "AI spin", "workout": _workout(45)}]}),
            say("Added."),
        ]
        turn = (await client.post(f"{base}/conversations", json={"content": "Add a spin"})).json()
        await client.post(f"{base}/proposals/{turn['messages'][-1]['proposal']['id']}/accept")
        ai_plan = next(p for p in (await coach.get(plans_url)).json() if p["title"] == "AI spin")
        assert ai_plan["can_edit"] is True and ai_plan["created_by_ai"] is True
        assert (await coach.patch(f"{plans_url}/{ai_plan['id']}", json={"title": "Coach's spin"})).status_code == 200
        mine_as_coach = next(p for p in (await coach.get(plans_url)).json() if p["title"] == "My ride")
        assert mine_as_coach["can_edit"] is False


async def test_a_proposal_gone_stale_is_refused(client, db_session, mistral_on, llm):
    athlete_id = await _ready(client, db_session)
    base = f"/athletes/{athlete_id}/ai-coach"
    plans_url = f"/athletes/{athlete_id}/planned-sessions"
    plan = (await client.post(plans_url, json={"planned_date": _future(2), "title": "Ride", "workout": _workout()["steps"]})).json()
    llm.script = [call("propose_changes", {"summary": "Skip it.", "ops": [{"op": "skip", "plan_id": plan["id"]}]}), say("ok")]
    proposal = (await client.post(f"{base}/conversations", json={"content": "skip"})).json()["messages"][-1]["proposal"]
    await client.delete(f"{plans_url}/{plan['id']}")
    stale = await client.post(f"{base}/proposals/{proposal['id']}/accept")
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "proposal_stale"
    assert (await client.post(f"{base}/proposals/{proposal['id']}/reject")).json()["status"] == "rejected"


# --- reports and replans ---------------------------------------------------------------------------


def test_the_weekly_report_is_due_after_the_chosen_moment():
    zone = ZoneInfo("America/Toronto")
    access = AiCoachAccess(weekly_reports=True, report_weekday=7, report_hour=19, approved_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    sunday_6pm = datetime(2026, 11, 15, 18, 0, tzinfo=zone)
    sunday_8pm = datetime(2026, 11, 15, 20, 0, tzinfo=zone)
    assert report_service.due_report_period(access, sunday_6pm, zone) == (date(2026, 11, 2), date(2026, 11, 8))
    assert report_service.due_report_period(access, sunday_8pm, zone) == (date(2026, 11, 9), date(2026, 11, 15))
    access.last_report_at = sunday_8pm
    assert report_service.due_report_period(access, sunday_8pm + timedelta(days=3), zone) is None
    access.report_weekday = 3  # Wednesday
    assert report_service.due_report_period(access, sunday_8pm + timedelta(days=3), zone) == (date(2026, 11, 12), date(2026, 11, 18))
    access.weekly_reports = False
    assert report_service.due_report_period(access, sunday_8pm + timedelta(days=3), zone) is None


async def test_the_worker_writes_the_weekly_report_once(client, db_session, mistral_on):
    athlete_id = await _ready(client, db_session)
    llm = FakeLlm(say("# Solid week\nYou did 3 of 3 sessions."))
    async with db_session() as session:
        assert await report_service.run_due_work(session, llm, uuid.UUID(athlete_id)) == "report"
    async with db_session() as session:
        assert await report_service.run_due_work(session, llm, uuid.UUID(athlete_id)) is None
        report = (await session.scalars(select(AiReport))).one()
        assert report.kind == "weekly" and report.content.startswith("# Solid week")
        notification = (await session.scalars(select(Notification))).one()
        assert notification.kind == "ai_report" and notification.payload["headline"] == "Solid week"
    assert "Task: write the training report" in llm.calls[0]["messages"][0]["content"]
    reports = (await client.get(f"/athletes/{athlete_id}/ai-coach/reports")).json()
    assert len(reports) == 1 and reports[0]["stats"]["plans"]["total"] == 0


async def test_missed_sessions_bring_a_replan_proposal(client, db_session, mistral_on):
    athlete_id = await _ready(client, db_session)
    async with db_session() as session:
        access = (await session.scalars(select(AiCoachAccess))).one()
        access.last_report_at = datetime.now(timezone.utc) - timedelta(days=2)
        access.weekly_reports = False
        for days, title in ((-2, "Missed intervals"), (2, "Coming ride")):
            session.add(
                PlannedSession(
                    athlete_id=uuid.UUID(athlete_id),
                    planned_date=date.today() + timedelta(days=days),
                    title=title,
                    workout=_workout()["steps"],
                    created_by_ai=True,
                )
            )
        await session.commit()
        coming = (await session.scalars(select(PlannedSession).where(PlannedSession.title == "Coming ride"))).one()

    def propose(messages, tools):
        assert "Missed intervals" in messages[-1]["content"]
        return call("propose_changes", {"summary": "Move the intervals to Friday.",
                                        "ops": [{"op": "update", "plan_id": str(coming.id), "date": _future(4)}]})

    llm = FakeLlm(propose, say("I moved things around."))
    async with db_session() as session:
        assert await report_service.run_due_work(session, llm, uuid.UUID(athlete_id)) == "replan"
    async with db_session() as session:
        proposal = (await session.scalars(select(AiProposal))).one()
        assert proposal.kind == "replan" and proposal.status == ProposalStatus.PENDING.value
        assert (await session.scalars(select(Notification))).one().kind == "ai_proposal"
        # Not again while it waits, nor within the cooldown.
        assert await report_service.run_due_work(session, FakeLlm(), uuid.UUID(athlete_id)) is None


# --- account ------------------------------------------------------------------------------------


async def test_export_and_deletion_cover_the_ai_coach(client, db_session, mistral_on, llm):
    athlete_id = await _ready(client, db_session)
    llm.script = [
        call("propose_changes", {"summary": "One ride.", "ops": [{"op": "create", "date": _future(1), "title": "Ride", "workout": _workout()}]}),
        say("Proposed."),
    ]
    await client.post(f"/athletes/{athlete_id}/ai-coach/conversations", json={"content": "plan a ride"})
    archive = zipfile.ZipFile(io.BytesIO((await client.get("/auth/me/export")).content))
    names = set(archive.namelist())
    assert {"ai_coach_access.csv", "ai_conversations.csv", "ai_messages.csv", "ai_proposals.csv", "ai_usage.csv"} <= names
    assert "plan a ride" in archive.read("ai_messages.csv").decode()

    me = (await client.get("/auth/me")).json()
    assert (await client.post("/auth/delete-account", json={"password": "Correcthorse123!"})).status_code == 204
    async with db_session() as session:
        assert await _rows_referencing(session, uuid.UUID(me["id"]), uuid.UUID(athlete_id)) == []
        assert (await session.scalars(select(AiMessage))).all() == []


def test_history_trim_keeps_the_current_turn_whole():
    from app.coach_ai.service import HISTORY_MESSAGES, _trim

    def message(role: str, seq: int) -> AiMessage:
        return AiMessage(role=role, content=str(seq), seq=seq, tool_call_id="t" if role == "tool" else None, name="n")

    history = [message("user", 0)] + [message("tool" if i % 2 else "assistant", i) for i in range(1, HISTORY_MESSAGES + 10)]
    sent = _trim(history, turn_start=0)
    assert sent[0] == {"role": "user", "content": "0"} and len(sent) == len(history)
    # Earlier turns start at a user message, never inside a tool exchange.
    older = [message("user", 0), message("assistant", 1)] * 30 + [message("user", 60)]
    sent = _trim(older, turn_start=len(older) - 1)
    assert sent[0]["role"] == "user" and len(sent) <= HISTORY_MESSAGES

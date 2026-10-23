"""The events that notify, one function each. They run inside the caller's
transaction (`service.notify` flushes, never commits) and choose the
recipients and the payload; whether and how a recipient hears about it is
their preferences' business.
"""

import uuid
from collections import defaultdict
from collections.abc import Collection
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus
from app.auth.models import User
from app.connections.models import (
    DataSourceConnection,
    IngestionRun,
    IngestionRunStatus,
    TransponderAssignment,
)
from app.db.base import utcnow
from app.notifications.kinds import NotificationKind
from app.notifications.models import Notification
from app.notifications.service import notify, notify_many
from app.training.insights import InsightKind
from app.training.insights_service import compute_insights, read_insights
from app.training.models import SessionComment, TrainingEvent

# Only recent records are announced: the first sync of a long history must
# not flood the bell with years of "new" records.
NEW_RECORD_WINDOW_DAYS = 7
# What is remembered as already announced (the window plus slack).
ANNOUNCED_LOOKBACK_DAYS = 30
MAX_RECORDS_PER_NOTIFICATION = 5
EXCERPT_LENGTH = 140
ERROR_LENGTH = 200


def _name_of(user: User, profile_name: str | None) -> str:
    return profile_name or user.email.split("@")[0]


async def _display_name(db: AsyncSession, user: User) -> str:
    return _name_of(user, await db.scalar(select(Athlete.display_name).where(Athlete.user_id == user.id)))


async def notify_new_records(
    db: AsyncSession, athlete_ids: Collection[uuid.UUID], *, today: date | None = None
) -> None:
    """Tells each athlete about the records their latest sync produced:
    one notification per session, listing up to five, and each record only
    ever once. Managed athletes have nobody to tell.
    """
    since = (today or date.today()) - timedelta(days=NEW_RECORD_WINDOW_DAYS)
    for athlete_id in athlete_ids:
        user_id = await db.scalar(select(Athlete.user_id).where(Athlete.id == athlete_id))
        if user_id is None:
            continue
        recent = [
            insight
            for insight in await compute_insights(db, athlete_id)
            if insight.kind == InsightKind.PERSONAL_RECORD and insight.event_date >= since
        ]
        if not recent:
            continue

        announced: set[str] = set()
        payloads = await db.scalars(
            select(Notification.payload).where(
                Notification.user_id == user_id,
                Notification.kind == NotificationKind.NEW_PR.value,
                Notification.created_at >= utcnow() - timedelta(days=ANNOUNCED_LOOKBACK_DAYS),
            )
        )
        for payload in payloads:
            announced.update(payload.get("insight_keys", []))
        fresh = [insight for insight in recent if insight.key not in announced]

        by_session: dict[uuid.UUID, list] = defaultdict(list)
        for insight in await read_insights(db, fresh):
            by_session[next(i.training_event_id for i in fresh if i.key == insight.key)].append(insight)
        for reads in by_session.values():
            first = reads[0]
            await notify(
                db,
                user_id,
                NotificationKind.NEW_PR,
                {
                    "external_event_id": first.external_event_id,
                    "session_name": first.session_name,
                    "event_date": first.event_date.isoformat(),
                    "count": len(reads),
                    "items": [
                        {
                            "event_key": read.event_key,
                            "start_type": read.start_type.value if read.start_type else None,
                            "time_ms": read.time_ms,
                            "previous_ms": read.previous_ms,
                            "milestone_ms": read.milestone_ms,
                            "track_name": read.track_name,
                        }
                        for read in reads[:MAX_RECORDS_PER_NOTIFICATION]
                    ],
                    "insight_keys": [read.key for read in reads],
                },
            )


async def notify_sync_failed(db: AsyncSession, connection_id: uuid.UUID, run_id: uuid.UUID, error_message: str) -> None:
    """A transponder's sync failed: tells whoever has it assigned right now,
    once per streak of failures (not again while the previous run failed too).
    """
    previous = await db.scalar(
        select(IngestionRun.status)
        .where(IngestionRun.data_source_connection_id == connection_id, IngestionRun.id != run_id)
        .order_by(IngestionRun.requested_at.desc())
        .limit(1)
    )
    if previous == IngestionRunStatus.FAILED:
        return
    connection = await db.get(DataSourceConnection, connection_id)
    if connection is None:
        return
    today = date.today()
    user_ids = set(
        await db.scalars(
            select(Athlete.user_id)
            .join(TransponderAssignment, TransponderAssignment.athlete_id == Athlete.id)
            .where(
                TransponderAssignment.data_source_connection_id == connection_id,
                TransponderAssignment.start_date <= today,
                (TransponderAssignment.end_date.is_(None)) | (TransponderAssignment.end_date >= today),
                Athlete.user_id.is_not(None),
            )
        )
    )
    await notify_many(
        db,
        user_ids,
        NotificationKind.SYNC_FAILED,
        {"transponder_code": connection.external_id, "error": error_message[:ERROR_LENGTH]},
        dedupe_key=f"sync_failed:{run_id}",
    )


async def notify_comment(db: AsyncSession, event: TrainingEvent, athlete: Athlete, author: User, body: str) -> None:
    """A comment on a session: the athlete, their active coaches and everyone
    already in the thread hear about it, except its author.
    """
    recipients: set[uuid.UUID] = set(
        await db.scalars(
            select(CoachAthlete.coach_user_id).where(
                CoachAthlete.athlete_id == athlete.id, CoachAthlete.status == CoachAthleteStatus.ACTIVE
            )
        )
    )
    recipients.update(await db.scalars(select(SessionComment.author_user_id).where(SessionComment.training_event_id == event.id)))
    if athlete.user_id is not None:
        recipients.add(athlete.user_id)
    recipients.discard(author.id)
    await notify_many(
        db,
        recipients,
        NotificationKind.COMMENT,
        {
            "author_name": await _display_name(db, author),
            "athlete_id": str(athlete.id),
            "athlete_name": athlete.display_name,
            "external_event_id": event.external_event_id,
            "session_name": event.title_override or event.name,
            "excerpt": body[:EXCERPT_LENGTH],
        },
    )


async def notify_coach_request(db: AsyncSession, link: CoachAthlete, athlete: Athlete, actor: User) -> None:
    """A coaching request is waiting for an answer: tells the side that has
    to give it. (Nothing for a managed athlete, which has no login.)
    """
    if link.status == CoachAthleteStatus.PENDING_ATHLETE_ACCEPTANCE:
        recipient, asked_role = athlete.user_id, "coach"
    elif link.status == CoachAthleteStatus.PENDING_COACH_ACCEPTANCE:
        recipient, asked_role = link.coach_user_id, "athlete"
    else:
        return
    if recipient is None or recipient == actor.id:
        return
    await notify(
        db,
        recipient,
        NotificationKind.COACH_REQUEST,
        {
            "from_name": await _display_name(db, actor),
            "asked_role": asked_role,  # who the request came from
            "athlete_id": str(athlete.id),
            "athlete_name": athlete.display_name,
        },
    )


async def notify_plan_added(db: AsyncSession, athlete: Athlete, author: User, title: str, planned_date: date) -> None:
    """Someone else planned a session for the athlete."""
    if athlete.user_id is None or athlete.user_id == author.id:
        return
    await notify(
        db,
        athlete.user_id,
        NotificationKind.PLAN_ADDED,
        {
            "author_name": await _display_name(db, author),
            "title": title,
            "planned_date": planned_date.isoformat(),
        },
    )

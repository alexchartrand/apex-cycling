"""The comment thread on an athlete's session. Whoever can reach the
athlete's data (`require_athlete_access`: the athlete, an active coach, a
club admin) can read and post; authors edit and delete their own, and the
athlete's side (the athlete, or a club admin for a managed athlete) can
delete any comment on their sessions.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.athletes.coaching import admin_club_ids, speaks_for_athlete
from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus, on_roster_of
from app.auth.models import User
from app.notifications.producers import notify_comment
from app.training.models import SessionComment, SessionCommentRead, TrainingEvent
from app.training.schemas import CommentInboxItem, CommentRead

EXCERPT_LENGTH = 140


async def find_event(db: AsyncSession, athlete_id: uuid.UUID, external_event_id: str) -> TrainingEvent | None:
    return await db.scalar(
        select(TrainingEvent).where(
            TrainingEvent.athlete_id == athlete_id, TrainingEvent.external_event_id == external_event_id
        )
    )


def _read(
    comment: SessionComment, author_name: str | None, athlete: Athlete, viewer: User, viewer_speaks_for_athlete: bool
) -> CommentRead:
    mine = comment.author_user_id == viewer.id
    return CommentRead(
        id=comment.id,
        author_user_id=comment.author_user_id,
        author_name=author_name,
        by_athlete=comment.author_user_id == athlete.user_id,
        body=comment.body,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
        can_edit=mine,
        can_delete=mine or viewer_speaks_for_athlete,
    )


async def list_comments(db: AsyncSession, event: TrainingEvent, athlete: Athlete, viewer: User) -> list[CommentRead]:
    speaks_for = await speaks_for_athlete(db, viewer, athlete)
    author_profile = aliased(Athlete)
    rows = await db.execute(
        select(SessionComment, author_profile.display_name)
        .outerjoin(author_profile, author_profile.user_id == SessionComment.author_user_id)
        .where(SessionComment.training_event_id == event.id)
        .order_by(SessionComment.created_at, SessionComment.id)
    )
    return [_read(c, name, athlete, viewer, speaks_for) for c, name in rows.all()]


async def add_comment(db: AsyncSession, event: TrainingEvent, athlete: Athlete, author: User, body: str) -> CommentRead:
    comment = SessionComment(training_event_id=event.id, author_user_id=author.id, body=body)
    db.add(comment)
    await db.flush()
    # Your own message means you've seen everything up to it.
    await mark_read(db, event, author)
    await notify_comment(db, event, athlete, author, body)
    await db.commit()
    own_profile = await db.scalar(select(Athlete.display_name).where(Athlete.user_id == author.id))
    return _read(comment, own_profile, athlete, author, await speaks_for_athlete(db, author, athlete))


async def _own_comment(db: AsyncSession, event: TrainingEvent, comment_id: uuid.UUID) -> SessionComment | None:
    comment = await db.get(SessionComment, comment_id)
    return comment if comment is not None and comment.training_event_id == event.id else None


class NotAllowed(Exception):
    pass


async def edit_comment(
    db: AsyncSession, event: TrainingEvent, athlete: Athlete, user: User, comment_id: uuid.UUID, body: str
) -> CommentRead | None:
    comment = await _own_comment(db, event, comment_id)
    if comment is None:
        return None
    if comment.author_user_id != user.id:
        raise NotAllowed("Only the author can edit a comment")
    comment.body, comment.edited_at = body, datetime.now(timezone.utc)
    await db.commit()
    name = await db.scalar(select(Athlete.display_name).where(Athlete.user_id == user.id))
    return _read(comment, name, athlete, user, await speaks_for_athlete(db, user, athlete))


async def delete_comment(
    db: AsyncSession, event: TrainingEvent, athlete: Athlete, user: User, comment_id: uuid.UUID
) -> bool:
    comment = await _own_comment(db, event, comment_id)
    if comment is None:
        return False
    if comment.author_user_id != user.id and not await speaks_for_athlete(db, user, athlete):
        raise NotAllowed("Only the author or the athlete can delete a comment")
    await db.delete(comment)
    await db.commit()
    return True


async def mark_read(db: AsyncSession, event: TrainingEvent, user: User) -> None:
    """Moves the user's read marker for this session to now. Doesn't commit."""
    marker = await db.scalar(
        select(SessionCommentRead).where(
            SessionCommentRead.user_id == user.id, SessionCommentRead.training_event_id == event.id
        )
    )
    now = datetime.now(timezone.utc)
    if marker is None:
        db.add(SessionCommentRead(user_id=user.id, training_event_id=event.id, last_read_at=now))
    else:
        marker.last_read_at = now


async def inbox(db: AsyncSession, user: User) -> list[CommentInboxItem]:
    """Sessions with comments from other people that the user hasn't read:
    their own sessions, those of athletes they coach, and those of the
    athletes of clubs they administer. Newest first."""
    admin_clubs = await admin_club_ids(db, user.id)
    coached = select(CoachAthlete.athlete_id).where(
        CoachAthlete.coach_user_id == user.id, CoachAthlete.status == CoachAthleteStatus.ACTIVE
    )
    reachable = or_(
        Athlete.user_id == user.id,
        Athlete.id.in_(coached),
        on_roster_of(admin_clubs),
    )
    author_profile = aliased(Athlete)
    rows = await db.execute(
        select(SessionComment, TrainingEvent, Athlete, author_profile.display_name)
        .join(TrainingEvent, TrainingEvent.id == SessionComment.training_event_id)
        .join(Athlete, Athlete.id == TrainingEvent.athlete_id)
        .outerjoin(author_profile, author_profile.user_id == SessionComment.author_user_id)
        .outerjoin(
            SessionCommentRead,
            and_(
                SessionCommentRead.training_event_id == TrainingEvent.id, SessionCommentRead.user_id == user.id
            ),
        )
        .where(
            reachable,
            SessionComment.author_user_id != user.id,
            or_(SessionCommentRead.id.is_(None), SessionComment.created_at > SessionCommentRead.last_read_at),
        )
        .order_by(SessionComment.created_at)
    )
    items: dict[uuid.UUID, CommentInboxItem] = {}
    for comment, event, athlete, author_name in rows.all():
        previous = items.get(event.id)
        excerpt = comment.body if len(comment.body) <= EXCERPT_LENGTH else comment.body[: EXCERPT_LENGTH - 1] + "…"
        items[event.id] = CommentInboxItem(
            athlete_id=athlete.id,
            athlete_name=athlete.display_name,
            external_event_id=event.external_event_id,
            event_name=event.title_override or event.name,
            event_date=event.event_date,
            unread_count=(previous.unread_count if previous else 0) + 1,
            latest_at=comment.created_at,
            latest_author_name=author_name,
            latest_excerpt=excerpt,
        )
    return sorted(items.values(), key=lambda item: item.latest_at, reverse=True)

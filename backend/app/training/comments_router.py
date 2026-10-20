import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.training import comments_service as comments
from app.training.models import TrainingEvent
from app.training.schemas import CommentInboxItem, CommentRead, CommentWrite

router = APIRouter(prefix="/athletes/{athlete_id}/sessions/{event_id}/comments", tags=["comments"])
inbox_router = APIRouter(prefix="/comments", tags=["comments"])


async def _event(
    event_id: str, athlete: Athlete = Depends(require_athlete_access), db: AsyncSession = Depends(get_db)
) -> TrainingEvent:
    event = await comments.find_event(db, athlete.id, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return event


@router.get("", response_model=list[CommentRead])
async def list_comments(
    event: TrainingEvent = Depends(_event),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CommentRead]:
    return await comments.list_comments(db, event, athlete, current_user)


@router.post("", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def add_comment(
    request: Request,
    payload: CommentWrite,
    event: TrainingEvent = Depends(_event),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentRead:
    return await comments.add_comment(db, event, athlete, current_user, payload.body)


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_thread_read(
    event: TrainingEvent = Depends(_event),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Called when the thread is shown: the inbox forgets what came before."""
    await comments.mark_read(db, event, current_user)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{comment_id}", response_model=CommentRead)
async def edit_comment(
    comment_id: uuid.UUID,
    payload: CommentWrite,
    event: TrainingEvent = Depends(_event),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentRead:
    try:
        edited = await comments.edit_comment(db, event, athlete, current_user, comment_id, payload.body)
    except comments.NotAllowed as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    if edited is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    return edited


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    event: TrainingEvent = Depends(_event),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        deleted = await comments.delete_comment(db, event, athlete, current_user, comment_id)
    except comments.NotAllowed as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@inbox_router.get("/inbox", response_model=list[CommentInboxItem])
async def comments_inbox(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[CommentInboxItem]:
    """Sessions with comments from other people I haven't read yet."""
    return await comments.inbox(db, current_user)

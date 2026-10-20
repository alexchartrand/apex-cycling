"""Editing a track's settings: the facts about the facility (length, indoor,
elevation, usual temperature) and which of its checkpoints and views are
displayed. Tracks are shared by everyone who rides there, so editing is
limited — see `can_edit_track`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.training.models import EventTrack, Track, TrainingLap
from app.training.records_service import recompute_many
from app.training.schemas import TrackSummary, TrackUpdate
from app.training.service import track_summary


def can_edit_track(user: User, track: Track) -> bool:
    """Platform admins only for now. Club admins of a club linked to the
    track's sqorz account join them with the club↔sqorz link (T4.1) — this is
    the one place that rule lives.
    """
    return user.is_platform_admin


class InvalidTrackSettings(Exception):
    pass


async def get_track(db: AsyncSession, track_id: uuid.UUID) -> Track | None:
    return await db.scalar(
        select(Track).where(Track.id == track_id).options(selectinload(Track.views), selectinload(Track.loops))
    )


async def update_track(db: AsyncSession, track: Track, payload: TrackUpdate, *, can_edit: bool) -> TrackSummary:
    """Applies the settings and commits. A changed length changes which
    records exist (multi-lap windows need it), so every athlete with laps on
    this track gets theirs recomputed.
    """
    changes = payload.model_dump(exclude_unset=True)

    hidden_loops = changes.pop("hidden_loop_ids", None)
    hidden_views = changes.pop("hidden_view_ids", None)
    if hidden_loops is not None and not set(hidden_loops) <= {loop.id for loop in track.loops}:
        raise InvalidTrackSettings("hidden_loop_ids contains a loop that isn't on this track")
    if hidden_views is not None and not set(hidden_views) <= {view.id for view in track.views}:
        raise InvalidTrackSettings("hidden_view_ids contains a view that isn't on this track")

    length_changed = "length_m" in changes and changes["length_m"] != track.length_m
    for field, value in changes.items():
        setattr(track, field, value)
    if hidden_loops is not None:
        for loop in track.loops:
            loop.hidden = loop.id in hidden_loops
    if hidden_views is not None:
        for view in track.views:
            view.hidden = view.id in hidden_views

    if length_changed:
        await db.flush()
        athlete_ids = (
            await db.scalars(
                select(TrainingLap.athlete_id)
                .join(EventTrack, EventTrack.id == TrainingLap.event_track_id)
                .where(EventTrack.track_id == track.id)
                .distinct()
            )
        ).all()
        await recompute_many(db, athlete_ids)

    await db.commit()
    return track_summary(track, can_edit=can_edit)

"""The plan answered by the ridden session: expands the plan's targets into
reps, scores each effort of the linked session, and matches them
(`matching.py`). Sqorz data only, so nothing here is Strava-derived.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.planning.matching import EffortResults, RepOutcome, RepStatus, expand_reps, match_reps
from app.planning.models import PlannedSession
from app.planning.schemas import PlanComparison, RepResult
from app.training.models import TrainingEvent
from app.training.records import session_results
from app.training.records_service import view_times_of
from app.training.service import _load_event_laps, detect_session_efforts


class NoLinkedSession(Exception):
    """The plan has no session to compare with."""


async def _effort_results(db: AsyncSession, plan: PlannedSession) -> list[EffortResults]:
    event = await db.get(TrainingEvent, plan.training_event_id)
    loaded = await _load_event_laps(db, plan.athlete_id, event.external_event_id) if event else None
    if loaded is None:
        return []
    event, laps = loaded
    laps_by_id = {lap.id: lap for lap in laps}
    results = []
    for index, (track, effort) in enumerate(detect_session_efforts(laps), start=1):
        results_of_effort = session_results(
            track_id=track.id,
            track_length_m=track.length_m,
            training_event_id=event.id,
            event_date=event.event_date,
            laps=list(effort.laps),
            view_times_ms=view_times_of(track, (laps_by_id[lap.lap_id] for lap in effort.laps)),
        )
        results.append(EffortResults(index, {(r.event_key, r.start_type): r.time_ms for r in results_of_effort}))
    return results


def _read(outcome: RepOutcome) -> RepResult:
    rep = outcome.rep
    return RepResult(
        target_index=rep.target_index,
        rep=rep.rep,
        label=rep.label,
        event_key=rep.event_key,
        target_time_ms=rep.target_time_ms,
        status=outcome.status,
        effort_index=outcome.effort_index,
        start_type=outcome.start_type,
        time_ms=outcome.time_ms,
        delta_ms=outcome.delta_ms,
    )


async def compare_plan(db: AsyncSession, plan: PlannedSession) -> PlanComparison:
    """Raises `NoLinkedSession`."""
    if plan.training_event_id is None:
        raise NoLinkedSession
    outcomes = match_reps(expand_reps(plan.targets or []), await _effort_results(db, plan))
    measured = [o for o in outcomes if o.rep.target_time_ms is not None and o.rep.event_key is not None]
    return PlanComparison(
        reps=[_read(o) for o in outcomes],
        measured=len(measured),
        hits=sum(1 for o in measured if o.status is RepStatus.HIT),
    )

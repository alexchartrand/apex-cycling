import hashlib
import json
import logging
from datetime import timedelta

from pydantic import TypeAdapter, ValidationError

from app.db.base import utcnow
from app.ingestion.common import UnitOfWorkPort
from app.ingestion.intervals.client import IntervalsAuthError, IntervalsClientError, IntervalsRateLimited
from app.ingestion.intervals.dtos import PlanPushJob, PushResult
from app.ingestion.intervals.ports import IntervalsCalendarPort, PlanPushRepositoryPort
from app.ingestion.intervals.workout_text import event_payload, event_uid
from app.workouts.schemas import WorkoutItem

logger = logging.getLogger("ingestion.intervals.push")

_ITEMS = TypeAdapter(list[WorkoutItem])

# Failed pushes wait 2, 4, 8… minutes, at most 6 hours, and stop after this
# many attempts until the plan changes again.
MAX_ATTEMPTS = 10
_MAX_DELAY = timedelta(hours=6)


def retry_delay(attempts: int) -> timedelta:
    """The wait after the `attempts`-th failure (1-based)."""
    return min(timedelta(minutes=2**attempts), _MAX_DELAY)


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class PlanPushService:
    """Keeps planned workouts on the athletes' Intervals.icu calendars (those
    who turned it on): for each plan marked due (`planning/push.py`), creates
    or updates its event, or deletes it once the plan is gone, skipped, has
    no workout left or the push was turned off. Only events we created are
    touched — by the id we got back, checked against our `uid`.

    Each plan is committed on its own. A failure is retried with a growing
    delay; a refused key stops that athlete's round, a rate limit the whole
    round (both wait for the next one).
    """

    def __init__(
        self,
        *,
        client: IntervalsCalendarPort,
        repo: PlanPushRepositoryPort,
        unit_of_work: UnitOfWorkPort,
        batch_size: int,
    ) -> None:
        self._client = client
        self._repo = repo
        self._unit_of_work = unit_of_work
        self._batch_size = batch_size

    async def run(self) -> PushResult:
        sent = removed = failed = 0
        refused: set = set()
        for job in await self._repo.due(utcnow(), self._batch_size):
            if job.connection_id in refused:
                continue
            try:
                outcome = await self._apply(job)
            except IntervalsRateLimited as exc:
                await self._unit_of_work.rollback()
                await self._repo.postpone(job.id, utcnow() + timedelta(seconds=exc.retry_after_s or 60))
                await self._unit_of_work.commit()
                return PushResult(sent, removed, failed + 1, rate_limited=True)
            except (IntervalsClientError, ValidationError) as exc:
                if isinstance(exc, IntervalsAuthError):
                    refused.add(job.connection_id)
                await self._fail(job, str(exc))
                failed += 1
                continue
            except Exception as exc:
                logger.exception("Pushing plan %s to Intervals.icu failed", job.plan_id)
                await self._fail(job, f"{type(exc).__name__}: {exc}")
                failed += 1
                continue
            await self._unit_of_work.commit()
            if outcome == "sent":
                sent += 1
            elif outcome == "removed":
                removed += 1
        return PushResult(sent, removed, failed)

    async def _fail(self, job: PlanPushJob, error: str) -> None:
        await self._unit_of_work.rollback()
        attempts = job.attempts + 1
        retry_at = utcnow() + retry_delay(attempts) if attempts < MAX_ATTEMPTS else None
        await self._repo.mark_failed(job.id, error, retry_at)
        await self._unit_of_work.commit()

    async def _apply(self, job: PlanPushJob) -> str | None:
        plan = job.plan
        wanted = job.push_enabled and plan is not None and bool(plan.workout) and plan.status != "skipped"
        if not wanted:
            if job.remote_event_id is not None:
                await self._client.delete_event(job.api_key, job.remote_event_id, event_uid(job.plan_id))
            await self._repo.forget(job.id)
            return "removed" if job.remote_event_id is not None else None

        payload = event_payload(
            plan_id=plan.id,
            title=plan.title,
            planned_date=plan.planned_date,
            description=plan.description,
            items=_ITEMS.validate_python(plan.workout),
            locale=job.locale,
        )
        digest = _hash(payload)
        if job.remote_event_id is not None and digest == job.payload_hash:
            await self._repo.mark_sent(job.id, job.remote_event_id, digest)  # nothing new to send
            return None
        event_id = await self._client.save_event(job.api_key, job.remote_event_id, payload)
        await self._repo.mark_sent(job.id, event_id, digest)
        return "sent"

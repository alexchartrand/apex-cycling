"""The worker's AI coach round: due weekly reports and replans, one athlete
at a time, each in its own session so one failure doesn't stop the rest."""

import logging
from collections.abc import Callable

from app.coach_ai.access import CapReached
from app.coach_ai.client import MistralClient, ai_coach_available
from app.coach_ai.ports import LlmClientPort, LlmError
from app.coach_ai.reports import run_due_work, scheduled_athletes
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("coach_ai.jobs")


async def run_ai_coach_round(
    session_factory: Callable = AsyncSessionLocal, client: LlmClientPort | None = None
) -> dict[str, int]:
    done = {"report": 0, "replan": 0, "failed": 0}
    if client is None:
        if not ai_coach_available():
            return done
        client = MistralClient()
    async with session_factory() as db:
        athlete_ids = await scheduled_athletes(db)
    for athlete_id in athlete_ids:
        try:
            async with session_factory() as db:
                what = await run_due_work(db, client, athlete_id)
        except CapReached:
            logger.info("AI coach: athlete %s is over this month's cap", athlete_id)
            done["failed"] += 1
            continue
        except LlmError as exc:
            logger.warning("AI coach: model call failed for athlete %s: %s", athlete_id, exc)
            done["failed"] += 1
            continue
        except Exception:
            logger.exception("AI coach: scheduled work failed for athlete %s", athlete_id)
            done["failed"] += 1
            continue
        if what:
            done[what] += 1
    return done

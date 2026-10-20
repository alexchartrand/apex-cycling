import logging

from fastapi import APIRouter, Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.router import router as activities_router
from app.admin.router import router as admin_router
from app.athletes.coach_router import router as coach_links_router
from app.athletes.router import router as athletes_router
from app.auth.router import router as auth_router
from app.clubs.router import invites_router
from app.clubs.router import router as clubs_router
from app.connections.router import ingestion_runs_router
from app.connections.router import router as connections_router
from app.core.config import API_PREFIX, get_settings
from app.core.logging import RequestLogMiddleware, configure_logging
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.training.comments_router import inbox_router as comments_inbox_router
from app.training.comments_router import router as comments_router
from app.training.records_router import router as records_router
from app.training.router import router as training_router
from app.training.tracks_router import router as tracks_router

logger = logging.getLogger("app.main")
settings = get_settings()
configure_logging()

app = FastAPI(
    title="ApexCycling API",
    version="0.1.0",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=None,
    openapi_url=f"{API_PREFIX}/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Outermost, so the request id covers CORS and rate-limit responses too.
app.add_middleware(RequestLogMiddleware)

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(auth_router)
api_router.include_router(athletes_router)
api_router.include_router(activities_router)
api_router.include_router(coach_links_router)
api_router.include_router(clubs_router)
api_router.include_router(invites_router)
api_router.include_router(connections_router)
api_router.include_router(ingestion_runs_router)
api_router.include_router(training_router)
api_router.include_router(records_router)
api_router.include_router(comments_router)
api_router.include_router(comments_inbox_router)
api_router.include_router(tracks_router)
api_router.include_router(admin_router)


@api_router.get("/health")
async def health(response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Deep health: the container healthcheck and uptime monitors use this, so
    it answers 503 when the database is unreachable.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "db": "unreachable"}
    return {"status": "ok", "db": "ok"}


app.include_router(api_router)

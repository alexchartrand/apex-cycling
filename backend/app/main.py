from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.athletes.coach_router import router as coach_links_router
from app.athletes.router import router as athletes_router
from app.auth.router import router as auth_router
from app.clubs.router import invites_router
from app.clubs.router import router as clubs_router
from app.connections.router import ingestion_runs_router
from app.connections.router import router as connections_router
from app.core.config import API_PREFIX, get_settings
from app.core.rate_limit import limiter
from app.training.records_router import router as records_router
from app.training.router import router as training_router
from app.training.tracks_router import router as tracks_router

settings = get_settings()

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

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(auth_router)
api_router.include_router(athletes_router)
api_router.include_router(coach_links_router)
api_router.include_router(clubs_router)
api_router.include_router(invites_router)
api_router.include_router(connections_router)
api_router.include_router(ingestion_runs_router)
api_router.include_router(training_router)
api_router.include_router(records_router)
api_router.include_router(tracks_router)


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)

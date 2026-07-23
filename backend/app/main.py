from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.athletes.router import router as athletes_router
from app.auth.router import router as auth_router
from app.connections.router import router as connections_router
from app.core.config import get_settings
from app.training.router import router as training_router

settings = get_settings()

app = FastAPI(title="Track Trainer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(athletes_router)
app.include_router(connections_router)
app.include_router(training_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

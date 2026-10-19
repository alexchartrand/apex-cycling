import os

# Must be set before `app.main` (and its transitive settings imports) load,
# since Settings() defaults cookie_secure to True and httpx's cookie jar
# won't send Secure cookies back over the test client's plain http:// base_url.
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401 -- registers all models on Base.metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # Every test hits /auth/login or /auth/signup from the same client IP
    # (127.0.0.1), so without resetting between tests, counts accumulate
    # across the whole run and later tests get spuriously rate-limited.
    app.state.limiter.reset()
    yield
    app.state.limiter.reset()


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session_factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as ac:
        yield ac

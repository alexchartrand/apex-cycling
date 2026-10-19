# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ApexCycling: a web app for track cycling training data. It ingests raw session
data from `my.sqorz.com` transponders (Strava/Garmin planned later, not yet
built), normalizes it into per-lap/per-segment training facts, and serves an
SPA with session detail + progression charts. Auth, club/athlete data model,
sqorz ingestion (manual + background polling), normalization, and charts are
built. Club-admin roster management and a coach dashboard are the last open
v1 milestone (M4b — see `BACKLOG.md`).

## Commands

Backend (from `backend/`, with `.venv` activated):
```bash
pip install -e ".[dev]"
python -m pytest                    # full suite (in-memory SQLite, no services needed)
python -m pytest tests/test_foo.py::test_name   # single test
ruff check .
alembic upgrade head                 # requires a real Postgres DATABASE_URL — migrations are Postgres-specific
uvicorn app.main:app --reload
python -m app.ingestion.runner       # background sqorz poller (APScheduler), optional for local dev
python -m app.db.seed                # seed a demo club/coach/athlete (password devpassword123 for all)
```

Frontend (from `frontend/`):
```bash
npm install
npm run dev
npm run build      # tsc -b && vite build — this is what CI runs, so a type error fails it
npm run lint       # oxlint
```

Full stack via Docker (recommended for manual/e2e testing):
```bash
cp .env.example .env
docker compose up --build   # db (Postgres 16), backend (:8000), worker, frontend (:5173)
```

CI (`.github/workflows/ci.yml`) runs backend `pytest` and frontend `npm run build` on every push/PR — no separate lint step in CI, so run `ruff`/`oxlint` locally.

For a SQLite dev DB (skipping Postgres/Alembic entirely), see `backend/tests/conftest.py::db_session` for the pattern: `create_async_engine("sqlite+aiosqlite:///:memory:")` + `Base.metadata.create_all`, then override the `get_db` FastAPI dependency.

## Backend architecture

Every router is mounted under `/api` (`API_PREFIX` in `app/core/config.py`, applied in `app/main.py`); route modules declare their prefixes without it. Tests' `AsyncClient` uses `base_url="http://test/api"` so test paths omit it too. In dev the Vite server proxies `/api` to the backend (`API_PROXY_TARGET`), in prod the edge Caddy does — the SPA always calls same-origin.

Domain modules under `backend/app/`: `auth`, `athletes`, `clubs`, `connections`, `ingestion`, `training`. Each (except `ingestion`) follows `models.py` / `schemas.py` / `router.py`, with a `service.py` where logic doesn't belong in the router.

**Model registration**: `app/db/models.py` re-exports every model class from every module purely so they register on `Base.metadata`. Any script or process that touches the ORM outside of going through `app.main` (seeding, one-off scripts, standalone test setups) must `import app.db.models` first, or SQLAlchemy relationship/FK resolution crashes at first use. `backend/tests/conftest.py` and `app/db/seed.py` both do this.

**Auth**: JWT access + refresh tokens in httponly cookies (`app/core/security.py`), not bearer headers. Access tokens are short-lived (15 min default); the frontend's `apiFetch` (`frontend/src/api/client.ts`) transparently retries once through `/auth/refresh` on a 401, coalescing concurrent refreshes into a single in-flight request. `app/auth/deps.py` provides `get_current_user`, plus `require_athlete_access` (athlete themself, their active coach, or their club's club_admin) and `require_club_admin` — route handlers needing athlete-scoped access must name the path parameter `athlete_id` for the dependency to bind correctly.

**Sqorz ingestion** (`app/ingestion/sqorz/`): being incrementally refactored to a ports/repository/DI pattern to decouple business logic from SQLAlchemy (see `BACKLOG.md` "Refactoring of backend"). Current shape for the client+service layer (step 1, done):
- `ports.py` — `Protocol` interfaces (`SqorzClientPort`, `*RepositoryPort`s, `SnapshotNormalizerPort`, `UnitOfWorkPort`). `service.py` must only depend on these, never on SQLAlchemy directly.
- `dtos.py` — plain dataclasses/records passed across the port boundary (e.g. `DataSourceConnectionRecord`, `IngestionRunRecord`).
- `repositories.py` — concrete SQLAlchemy-backed implementations of the repo ports.
- `normalizer_adapter.py` — adapts the concrete `normalizer.py` (still un-refactored, see below) to `SnapshotNormalizerPort`.
- `factory.py` — the one composition root (`build_sqorz_ingestion_service`) wiring concrete adapters into `SqorzIngestionService`; nothing else should construct that service directly.
- `service.py` — `SqorzIngestionService.ingest`: fetch → dedupe by content hash against the latest stored `RawSnapshot` → always re-normalize the fetched payload regardless of hash match (so a newly-added `TransponderAssignment` retroactively attributes previously-unowned laps) → mark the `IngestionRun` success/failed → commit.
- `normalizer.py` — the actual sqorz-payload → training-tables normalization logic; **not yet refactored** to the ports pattern (deferred, same pattern to reuse when picked up).

Tests for the refactored layer (`backend/tests/test_sqorz_ingestion_service.py`) fake every port directly — no DB, no HTTP — as the reference pattern for testing this style of service.

`app/ingestion/jobs.py::poll_active_connections` (invoked by `app/ingestion/runner.py`'s APScheduler loop) only polls sqorz connections with a currently-active `TransponderAssignment` (assignment window covers today).

**Training data model** (`app/training/models.py`): `Track`/`TrackLoop`/`TrackView`/`TrackViewLoop` are a shared facility dimension scoped by sqorz's `account_id` (not by apex-cycling `club_id` — a session can span athletes from many or no clubs). `TrainingEvent` and everything under it (`EventClass`, `EventTrack`, `TrainingLap`, `LapSegmentTime`) is instead a private per-athlete copy — two athletes at the same physical sqorz event each get independent rows, since this data is meant to be manually editable per-athlete without side effects. `LapSegmentTime.time_ms` is cumulative elapsed time since lap start (matches sqorz's `lapTimes` 1:1) — never sum it directly; whole-lap/view/segment durations are derived by boundary subtraction in `app/training/service.py` (`_whole_lap_time_ms`, `_view_time_ms`, `_segment_deltas`).

## Frontend architecture

Vite + React 19 + TypeScript, feature-folder structure under `src/features/<domain>/` (`api.ts`, `types.ts`, `use<Domain>.ts` hooks using TanStack Query), with route components in `src/routes/`. `src/api/client.ts::apiFetch` is the sole fetch wrapper — it handles the cookie-based auth refresh dance described above; new API calls should go through it rather than raw `fetch`. Routing (`src/App.tsx`) gates everything except `/login` and `/signup` behind `ProtectedRoute`, wrapped in the `AppShell` layout.

## Conventions

- Don't commit `Co-Authored-By: Claude` trailers in git commit messages for this repo.
- `BACKLOG.md` is the maintained backlog (bugs/features/deferred/done) — check it for current priorities and add items there rather than a separate tracker.

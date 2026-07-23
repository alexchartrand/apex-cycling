# Track Trainer

Web app for track cycling training data: visualize progression from `my.sqorz.com`
transponder data (Strava/Garmin and training recommendations planned for later).
See `docs/plan.md`-equivalent context in the original architecture plan for the
full design; this file just covers running what's built so far (M1: auth +
club/athlete data model foundation; M2: sqorz raw ingestion — report a
transponder + date range, pull its training history, background polling).

## Run with Docker (recommended)

Requires Docker with Compose. On WSL, enable Docker Desktop's WSL integration
first (`docker`/`docker compose` aren't available in a bare WSL distro).

```bash
cp .env.example .env   # adjust JWT_SECRET for anything beyond local dev
docker compose up --build
```

This starts four services:

- `db` — Postgres 16, localhost:5432 (user/pass/db: `track_trainer`)
- `backend` — FastAPI, http://localhost:8000 (docs at `/docs`). Runs
  migrations automatically on start.
- `worker` — background APScheduler process that polls sqorz for any
  transponder with a currently-active assignment (no exposed port).
- `frontend` — http://localhost:5173

To seed a demo club/coach/athlete roster (all accounts use password
`devpassword123`):

```bash
docker compose exec backend python -m app.db.seed
```

Then sign up (or log in as a seeded user), go to the dashboard, and use
"Transponder usage" to report a transponder code + date range — e.g. the
real sample transponder `LS-03407` — which triggers an immediate sync and
persists the raw sqorz response for that connection.

**Not yet verified**: this Docker/Postgres path hasn't actually been run in
the sandbox that built it — only its generated SQL and SQLite-backed logic
were checked. Please run `docker compose up --build` yourself and report
back if anything breaks.

## Run without Docker (manual dev)

Backend (requires a running Postgres reachable at `DATABASE_URL`, or point
`DATABASE_URL` at SQLite for quick local testing, e.g.
`sqlite+aiosqlite:///./dev.db` — note the Alembic migrations are
Postgres-specific, so for a SQLite dev DB create tables directly instead of
running `alembic upgrade head`, see `backend/tests/conftest.py` for the pattern):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head        # against a real Postgres DATABASE_URL
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Ingestion worker (optional — only needed to test background polling; the
"report usage" endpoint already triggers an immediate import on its own):

```bash
cd backend
source .venv/bin/activate
python -m app.ingestion.runner
```

## Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest
```

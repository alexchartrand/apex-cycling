# ApexCycling

Web app for track cycling training data: visualize progression from `my.sqorz.com`
transponder data (Strava/Garmin and training recommendations planned for later).
See `docs/plan.md`-equivalent context in the original architecture plan for the
full design; this file just covers running what's built so far — auth +
club/athlete data model foundation, sqorz raw ingestion (report a
transponder + date range, pull its training history, background polling),
normalization into per-lap/per-segment training data, clubs and coaching,
and an SPA with session detail, records and progression charts.

## Run with Docker (recommended)

Requires Docker with Compose. On WSL, enable Docker Desktop's WSL integration
first (`docker`/`docker compose` aren't available in a bare WSL distro).

```bash
cp .env.example .env   # adjust JWT_SECRET for anything beyond local dev
docker compose up --build
```

This starts four services:

- `db` — Postgres 16, localhost:5432 (user/pass/db: `apex_cycling`)
- `backend` — FastAPI, http://localhost:8000 (every route under `/api`,
  docs at `/api/docs`). Runs migrations automatically on start.
- `worker` — background APScheduler process that polls sqorz for any
  transponder with a currently-active assignment (no exposed port).
- `frontend` — http://localhost:5173 (the Vite dev server proxies `/api` to
  the backend, so the SPA and API share one origin, same as in production)

To seed a demo club/coach/athlete roster (all accounts use password
`devpassword123`):

```bash
docker compose exec backend python -m app.db.seed
```

Then sign up (or log in as a seeded user), go to the dashboard, and use
"Transponder usage" to report a transponder code + date range — e.g. the
real sample transponder `LS-03407` — which triggers an immediate sync and
persists the raw sqorz response for that connection.

This stack has been built and run for real with `docker compose up --build`
(not just checked offline), and the full signup → report transponder usage
→ import → sessions list → session detail → progression flow has been
driven end-to-end through a live browser against it.

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

## Production deployment

The production stack (Caddy + backend + worker + Postgres + backup on a single
VPS, `apex-cycling.net`) is documented in **[deploy.md](deploy.md)**: the tag-and-deploy release flow, rollback, backups and restore,
optional Strava/SMTP/push setup, and troubleshooting.

```bash
git tag -a vX.Y.Z -m "vX.Y.Z: <summary>" && git push origin master vX.Y.Z   # dev machine
scripts/deploy.sh                                                           # on the server
```

## Continuous integration

`.github/workflows/ci.yml` runs on every push/PR: backend `pytest` (against
the same in-memory SQLite tests use locally, no services needed) and a
frontend `npm run build` (`tsc -b && vite build`, so a broken type or build
fails CI). Push this repo to GitHub for the workflow to actually run.

## Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest
```

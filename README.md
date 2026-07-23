# Track Trainer

Web app for track cycling training data: visualize progression from `my.sqorz.com`
transponder data (Strava/Garmin and training recommendations planned for later).
See `docs/plan.md`-equivalent context in the original architecture plan for the
full design; this file just covers running what's built so far — auth +
club/athlete data model foundation, sqorz raw ingestion (report a
transponder + date range, pull its training history, background polling),
normalization into per-lap/per-segment training data, and an SPA with
session detail + progression charts. Club-admin roster management and a
coach dashboard are not built yet.

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

`docker-compose.prod.yml` builds multi-stage, non-dev images (no bind mounts,
no `--reload`, no dev dependencies) and fronts the whole stack with a single
[Caddy](https://caddyserver.com/) container that serves the built frontend
and reverse-proxies backend routes (`/auth`, `/athletes`, `/health` — see
`docker/Caddyfile`) on the same origin, so the browser never makes a
cross-origin request and no CORS configuration is needed in production.
Caddy also handles TLS automatically: point a real domain's DNS at the host
and it gets a Let's Encrypt certificate on first request, no manual
cert/reverse-proxy setup required. Hosting provider is still an open
choice — this compose file works unchanged on any host that can run Docker
and reach the internet on ports 80/443.

```bash
cp .env.prod.example .env.prod   # fill in DOMAIN, JWT_SECRET, POSTGRES_PASSWORD
docker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d
```

Every secret in `.env.prod` (`JWT_SECRET`, `POSTGRES_PASSWORD`) has no
fallback default — compose refuses to start until they're set. Run
migrations happen automatically on backend startup, same as dev.

This exact compose file has been built and run end-to-end in this
repository (own project name `track-trainer-prod` so it never shares a
network or volume with the dev stack): db/backend/worker/frontend all come
up healthy, `GET /health` and the SPA both serve correctly through Caddy's
TLS (self-signed for `localhost`, real Let's Encrypt for a real domain), and
a full signup → cookie-authenticated request round-trip works through the
proxy.

**Not yet exercised for real**: actually pointing a public DNS record at a
host and confirming Let's Encrypt issues a real certificate (the local
verification above only confirms Caddy *would* request one — `localhost`
gets Caddy's internal/self-signed cert instead since it isn't a public
domain).

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

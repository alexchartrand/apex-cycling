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
npm test           # vitest (jsdom + Testing Library, setup in src/test/setup.ts)
```

Full stack via Docker (recommended for manual/e2e testing):
```bash
cp .env.example .env
docker compose up --build   # db (Postgres 16), backend (:8000), worker, frontend (:5173)
```

CI (`.github/workflows/ci.yml`, on push to `master` and PRs) runs backend `ruff` + `pytest`, a Postgres job doing `alembic upgrade head` → `alembic check` (fails if models drifted from migrations) → `downgrade base` → `upgrade head`, and frontend `lint` + `test` + `build`. Every new migration must keep that round-trip and `alembic check` clean.

The backend `.venv` console scripts have stale shebangs from the Track Trainer rename — use `.venv/bin/python -m alembic` / `-m pytest` rather than `.venv/bin/alembic`.

For a SQLite dev DB (skipping Postgres/Alembic entirely), see `backend/tests/conftest.py::db_session` for the pattern: `create_async_engine("sqlite+aiosqlite:///:memory:")` + `Base.metadata.create_all`, then override the `get_db` FastAPI dependency.

## Backend architecture

Every router is mounted under `/api` (`API_PREFIX` in `app/core/config.py`, applied in `app/main.py`); route modules declare their prefixes without it. Tests' `AsyncClient` uses `base_url="http://test/api"` so test paths omit it too. In dev the Vite server proxies `/api` to the backend (`API_PROXY_TARGET`), in prod the edge Caddy does — the SPA always calls same-origin.

Domain modules under `backend/app/`: `auth`, `athletes`, `clubs`, `connections`, `ingestion`, `training`. Each (except `ingestion`) follows `models.py` / `schemas.py` / `router.py`, with a `service.py` where logic doesn't belong in the router.

**Model registration**: `app/db/models.py` re-exports every model class from every module purely so they register on `Base.metadata`. Any script or process that touches the ORM outside of going through `app.main` (seeding, one-off scripts, standalone test setups) must `import app.db.models` first, or SQLAlchemy relationship/FK resolution crashes at first use. `backend/tests/conftest.py` and `app/db/seed.py` both do this.

**Auth**: JWT access + refresh tokens in httponly cookies (`app/core/security.py`), not bearer headers. Access tokens are short-lived (15 min default); the frontend's `apiFetch` (`frontend/src/api/client.ts`) transparently retries once through `/auth/refresh` on a 401, coalescing concurrent refreshes into a single in-flight request. `app/auth/deps.py` provides `get_current_user`, plus `require_athlete_access` (athlete themself, their active coach, or their club's club_admin) and `require_club_admin` — route handlers needing athlete-scoped access must name the path parameter `athlete_id` for the dependency to bind correctly.

**Sessions & account** (`app/auth/`): a password change/reset sets `users.credentials_changed_at`, and any access/refresh token issued before it is rejected (`issued_before_credentials_change`) — that is how other devices get signed out. Reset links are single-use, hashed `PasswordResetToken` rows carried in the URL fragment; email goes out only when `SMTP_HOST`+`SMTP_FROM` are set (`app/core/mail.py`), otherwise a platform/club admin issues a link (`POST /auth/users/{id}/password-reset-link`) or the operator runs `python -m app.auth.cli reset-link <email>`. `app/auth/account.py` holds "export my data" and "delete account": **any new table with a `user_id`/`athlete_id` FK must be added to both** (`tests/test_account.py` fails if a row still points at a deleted user/athlete). The login/signup/reset/change/delete routes are rate-limited at 5–10/min per IP, which also bites repeated manual or Playwright runs — restart the backend to reset the in-memory counters.

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

**Efforts, distances & records** (`app/training/`): pure, directly-tested modules with the DB-facing parts split off — `efforts.py` (group laps into continuous efforts: next lap starts where the previous ended, an unfinished lap always ends its effort; standing vs flying from the first-lap time profile because sqorz's `from_start` is True on every lap; P1/P2 half-lap splits across the whole effort), `distances.py` (`STANDARD_EVENTS`; N-lap windows inside an effort, N = distance / `Track.length_m`, so tracks without a length only get single-lap/F200 records), `records.py` (per-session results → all-time best → improvement chain). `records_service.py` persists `personal_records` (derived, rebuilt by `recompute_personal_records`, never edited) and CRUD for `manual_results`; the board merges both, best time per place/event/start type. `SqorzIngestionService` recomputes records for the athletes `normalize` reports via `AthleteRecordsPort`; after any change to laps or `length_m` run `python -m app.training.cli recompute-records [--athlete ID]`. Athlete edits (`edit_service.py`; columns on `TrainingEvent`/`TrainingLap` that the sqorz upsert never writes, so they survive re-syncs): session `title_override`/notes/RPE/tags, lap `excluded`/`label`, and `effort_label` on the *first lap of an effort* (efforts are computed, so there's no row to hang it on). An excluded lap stays in its effort so neighbours stay chained, but never counts as a best lap, in a record window, the F200 or progression; toggling it recomputes records. Track settings (`tracks_service.py`, `PATCH /api/tracks/{id}`): `Track.length_m`/`indoor`/`elevation_m`/`default_temp_c` plus a `hidden` flag on loops (not drawn on the diagram) and views (not offered in pickers) — display-only, never written by sync; new loops named "Courbe…" start hidden (`DEFAULT_HIDDEN_LOOP_PREFIXES` in the normalizer). `can_edit_track` is the single permission rule (platform admin only until the club↔sqorz link exists, T4.1); grant it with `python -m app.auth.cli grant-admin <email>`. Changing `length_m` recomputes records for every athlete with laps on the track. Tracks are shared rows, so one edit shows for everyone who rode there. Real fixture facts: `tests/fixtures/LS-03407.json` has two distinct tracks both named "Tour complet" (different sqorz ids), so a records board can show the same place name twice.

## Frontend architecture

**Design system**: all styling goes through semantic tokens in `src/theme/tokens.css` (`--color-*`, `--chart-*`, `--space-*`, `--radius-*`, `--text-*`), defined for both `data-theme="light"` (paper) and `"dark"` (night session) — never use raw `--apex-*` palette values in components, or dark mode breaks. Reusable components live in `src/components/ui/` (Radix-based Dialog/Menu/Tabs/Tooltip/Toast, DataTable, StatTile, form fields…) and chart helpers in `src/components/charts/` (`axisProps`/`gridProps`/`ChartTooltip`/`ChartFrame`). `var()` works in Recharts stroke/fill props but **not** in gradient `<stop>` colors — use flat `fill` + `fillOpacity`. **Velodrome diagram**: `features/training/VelodromeDiagram.tsx` renders geometry from the pure, unit-tested `velodromeGeometry.ts` — a clothoid-transition track model (s = 0 at mid home straight where P1 sits, s increasing counterclockwise on a y-down screen), loop placement (`placeLoops`: length_m or furthest checkpoint, `NNNm` names = remaining distance to finish, P1 anchoring), and collision-avoiding label layout. Change placement rules there, with tests, not in the component.

**i18n** (FR/EN): i18next with per-namespace TS resource files in `src/i18n/locales/{en,fr}/` — English is the source of truth, and each French file `satisfies LocaleNamespace<typeof en>` so missing/extra keys fail `tsc`; `t()` keys are type-checked too (`src/i18n/i18next.d.ts`). Register new namespaces in `src/i18n/locales/index.ts`. Format numbers/dates/lap times only via `useFormat()` (`src/i18n/format.ts`: French uses a decimal comma, and `parseLocalDate` avoids the UTC off-by-one-day bug for `YYYY-MM-DD` strings). Request errors go through `errorMessage()` (`src/api/errors.ts`), mapping known HTTP statuses to translated text. The dev-only `/styleguide` route shows every component in both themes. The dev frontend container reinstalls npm deps on start (anonymous `node_modules` volume), so a new dependency just needs `docker compose restart frontend`.

Vite + React 19 + TypeScript, feature-folder structure under `src/features/<domain>/` (`api.ts`, `types.ts`, `use<Domain>.ts` hooks using TanStack Query), with route components in `src/routes/`. `src/api/client.ts::apiFetch` is the sole fetch wrapper — it handles the cookie-based auth refresh dance described above; new API calls should go through it rather than raw `fetch`. Routing (`src/App.tsx`) gates everything except `/login` and `/signup` behind `ProtectedRoute`, wrapped in the `AppShell` layout.

## Conventions

- Don't commit `Co-Authored-By: Claude` trailers in git commit messages for this repo.
- `BACKLOG.md` is the maintained backlog (bugs/features/deferred/done) — check it for current priorities and add items there rather than a separate tracker.

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

Production (single VPS, see README "Production deployment"; scripts in `scripts/`):
```bash
sudo scripts/server-setup.sh                      # once, bare Ubuntu 24.04 (Docker, ufw, fail2ban, swap)
scripts/init-env.sh <domain> <email>              # writes .env.prod with fresh secrets
scripts/deploy.sh [--no-pull|--rollback]          # build, back up, up --wait, health check, auto-rollback
scripts/compose.sh <compose args>                 # docker compose against the deployed image tag
sudo scripts/restore.sh latest                    # replaces ALL data from the newest backup
scripts/compose.sh exec backend python -m app.auth.cli create-admin <email> "<name>"
```

Browser smoke tests (from `e2e/`, Playwright; any base URL, deletes the account it signs up):
```bash
npm install && npx playwright install chromium   # once
E2E_BASE_URL=https://apex-cycling.net E2E_EDGE=1 npm test   # E2E_EDGE=1 also asserts Caddy's headers; default target is the dev stack on :5173
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

**Ops & prod** (`docker-compose.prod.yml`, `docker/Caddyfile`, `app/ops/`, `app/admin/`, `app/core/logging.py`): Caddy is the only published service (80/443, automatic Let's Encrypt; `DOMAIN=localhost` gives a private-CA cert for smoke tests) and ports are published on IPv4 only (Docker's IPv6 proxy would hide client IPs — publish an A record, never AAAA) and the compose network is pinned to `172.28.0.0/24` so uvicorn's `FORWARDED_ALLOW_IPS` trusts only Caddy — that is what makes slowapi's `get_remote_address` see the real client (`tests/test_rate_limit_proxy.py`). Images are tagged `APP_TAG` = git commit (+ `-dirty-<diffhash>`), kept in `.deployed-tag`; always use `scripts/compose.sh` instead of bare `docker compose` or you get the `latest` tag. CSP is `script-src 'self'`, so no inline scripts in `frontend/index.html` (the theme pre-paint script is `public/theme-init.js`). The worker writes `/tmp/worker-heartbeat` (container healthcheck) and a `worker_heartbeats` row (admin page) every minute; `/api/health` does `SELECT 1`; logs are JSON when `LOG_FORMAT=json`, each request carrying `request_id` (Caddy sets `X-Request-ID`). Backups live in `/var/backups/apex-cycling` (root-owned) from `docker/backup.sh`; a new uploads directory the backend writes to must be created and chowned in `backend.prod.Dockerfile` (`/data/uploads` is) or the named volume comes up root-only. Platform-admin API: `GET /api/admin/overview` (`require_platform_admin`), page at `/admin` linked from the account menu.

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

**Clubs** (`app/clubs/`): any user can create a club and becomes its `club_admin` (`ClubRole`: athlete / coach / club_admin). Joining as an athlete puts the user's self-athlete on the roster (`Athlete.club_id`, one club per profile; leaving or a role change off `athlete` clears it); managed athletes are `Athlete` rows with `user_id` null that club admins create (`POST /clubs/{id}/athletes`) and then run through the normal `/athletes/{id}/…` endpoints (profile, metrics, transponders) via `require_athlete_access`. Invites (`club_invites`) are hashed tokens carried in the URL fragment (`/join#token=…`), role athlete or coach only (admins are promoted in the member list), with expiry and `max_uses`; preview/accept take the token in the request body (`/api/invites/preview|accept`) so it stays out of access logs; email goes out when SMTP is set, otherwise the admin copies the link. A club always keeps ≥1 admin (demote/remove/delete-account are refused for the last one while the club has other people or managed athletes; a one-person club is deleted with its account — `clubs/service.py`). `club_sqorz_accounts` links a club to a sqorz facility so its admins can edit that facility's tracks; only platform admins create links (API or `python -m app.clubs.cli link-sqorz <slug> <account-id>`). `auth/account.py::delete_athlete` is the shared "remove an athlete and all their data" used by account deletion and managed-athlete deletion — new athlete-owned tables go there and in `build_export`.

**Coach–athlete links** (`app/athletes/coaching.py`, `coach_router.py`, `/api/coach-links`): a link needs both sides — whoever asks creates it pending on the other side (`pending_athlete_acceptance` when a coach asks, `pending_coach_acceptance` when the athlete does); the other side accepts, or declines/cancels/revokes via `/revoke` (all end `REVOKED`; asking again reopens the same row); both sides having asked activates it. Only `ACTIVE` links grant access (`require_athlete_access`). A managed athlete has no login, so their club's admins speak for them: an admin assigns a coach of the club and the link is active at once (`speaks_for_athlete`). `POST /coach-links` takes `acting_as` coach|athlete and names the other person by id (limited to people you share a club with — roster for coaches, coach/admin members for athletes) or by email; the email form always answers the same 202 so it can't reveal which addresses have accounts. `GET /coach-links/{athletes,coaches,inbox}` list my athletes, my coaches (optionally of a managed athlete) and requests waiting for my answer; `GET /coach-links/dashboard` (`athletes/dashboard.py`) is the coach's summary card per actively-coached athlete (last session, this vs previous 7 days' sessions/laps/avg RPE — "form" is recent load, not a fitness model — records in the last 14 days, transponders whose latest sync failed, unread comments).

**Session comments** (`app/training/comments_*.py`, `/api/athletes/{id}/sessions/{event}/comments`, `/api/comments/inbox`): a thread per athlete session (`SessionComment` hangs off the private `TrainingEvent`) between the athlete and anyone passing `require_athlete_access` (active coach, club admin). Authors edit/delete their own; the athlete's side (`speaks_for_athlete` — the athlete, or a club admin for a managed athlete) can delete any. "New" is tracked per (user, session) by `SessionCommentRead.last_read_at` (`POST …/comments/read` when the thread is shown; posting also marks it read); the inbox lists sessions with unread comments by others across the user's own athlete, athletes they actively coach and clubs they administer. Deleting an account deletes the comments it wrote; deleting an athlete deletes the threads on their sessions.

**Training data model** (`app/training/models.py`): `Track`/`TrackLoop`/`TrackView`/`TrackViewLoop` are a shared facility dimension scoped by sqorz's `account_id` (not by apex-cycling `club_id` — a session can span athletes from many or no clubs). `TrainingEvent` and everything under it (`EventClass`, `EventTrack`, `TrainingLap`, `LapSegmentTime`) is instead a private per-athlete copy — two athletes at the same physical sqorz event each get independent rows, since this data is meant to be manually editable per-athlete without side effects. `LapSegmentTime.time_ms` is cumulative elapsed time since lap start (matches sqorz's `lapTimes` 1:1) — never sum it directly; whole-lap/view/segment durations are derived by boundary subtraction in `app/training/service.py` (`_whole_lap_time_ms`, `_view_time_ms`, `_segment_deltas`).

**Frontend records & session page**: `features/records/` (board grouped by place, record-history step chart, manual-result dialog; `timeInput.ts` parses typed times like `1:12,345`) and `features/training/session/` (Overview / Laps / Efforts / Notes / Comments tabs, `?tab=` in the URL; `lapTable.ts` builds the split columns and the CSV). The Progress page maps standard events to `custom_distance` + `start_type` in `features/training/progression.ts` and only offers them for tracks with a length set. Pure helpers live in plain `.ts` files next to the components (lint's only-export-components rule).

**Efforts, distances & records** (`app/training/`): pure, directly-tested modules with the DB-facing parts split off — `efforts.py` (group laps into continuous efforts: next lap starts where the previous ended, an unfinished lap always ends its effort; standing vs flying from the first-lap time profile because sqorz's `from_start` is True on every lap; P1/P2 half-lap splits across the whole effort), `distances.py` (`STANDARD_EVENTS`; N-lap windows inside an effort, N = distance / `Track.length_m`, so tracks without a length only get single-lap/F200 records), `records.py` (per-session results → all-time best → improvement chain). `records_service.py` persists `personal_records` (derived, rebuilt by `recompute_personal_records`, never edited) and CRUD for `manual_results`; the board merges both, best time per place/event/start type. `SqorzIngestionService` recomputes records for the athletes `normalize` reports via `AthleteRecordsPort`; after any change to laps or `length_m` run `python -m app.training.cli recompute-records [--athlete ID]`. Athlete edits (`edit_service.py`; columns on `TrainingEvent`/`TrainingLap` that the sqorz upsert never writes, so they survive re-syncs): session `title_override`/notes/RPE/tags, lap `excluded`/`label`, and `effort_label` on the *first lap of an effort* (efforts are computed, so there's no row to hang it on). An excluded lap stays in its effort so neighbours stay chained, but never counts as a best lap, in a record window, the F200 or progression; toggling it recomputes records. Track settings (`tracks_service.py`, `PATCH /api/tracks/{id}`): `Track.length_m`/`indoor`/`elevation_m`/`default_temp_c` plus a `hidden` flag on loops (not drawn on the diagram) and views (not offered in pickers) — display-only, never written by sync; new loops named "Courbe…" start hidden (`DEFAULT_HIDDEN_LOOP_PREFIXES` in the normalizer). `TrackEditRights` (`track_edit_rights(db, user)` once per request, then `.can_edit(track)`) is the single permission rule: platform admins, or admins of a club linked to the track's `sqorz_account_id` via `club_sqorz_accounts`; grant platform admin with `python -m app.auth.cli grant-admin <email>`. Changing `length_m` recomputes records for every athlete with laps on the track. Tracks are shared rows, so one edit shows for everyone who rode there. Real fixture facts: `tests/fixtures/LS-03407.json` has two distinct tracks both named "Tour complet" (different sqorz ids), so a records board can show the same place name twice.

## Frontend architecture

**Design system**: all styling goes through semantic tokens in `src/theme/tokens.css` (`--color-*`, `--chart-*`, `--space-*`, `--radius-*`, `--text-*`), defined for both `data-theme="light"` (paper) and `"dark"` (night session) — never use raw `--apex-*` palette values in components, or dark mode breaks. Reusable components live in `src/components/ui/` (Radix-based Dialog/Menu/Tabs/Tooltip/Toast, DataTable, StatTile, form fields…) and chart helpers in `src/components/charts/` (`axisProps`/`gridProps`/`ChartTooltip`/`ChartFrame`). `var()` works in Recharts stroke/fill props but **not** in gradient `<stop>` colors — use flat `fill` + `fillOpacity`. **Velodrome diagram**: `features/training/VelodromeDiagram.tsx` renders geometry from the pure, unit-tested `velodromeGeometry.ts` — a clothoid-transition track model (s = 0 at mid home straight where P1 sits, s increasing counterclockwise on a y-down screen), loop placement (`placeLoops`: length_m or furthest checkpoint, `NNNm` names = remaining distance to finish, P1 anchoring), and collision-avoiding label layout. Change placement rules there, with tests, not in the component.

**i18n** (FR/EN): i18next with per-namespace TS resource files in `src/i18n/locales/{en,fr}/` — English is the source of truth, and each French file `satisfies LocaleNamespace<typeof en>` so missing/extra keys fail `tsc`; `t()` keys are type-checked too (`src/i18n/i18next.d.ts`). Register new namespaces in `src/i18n/locales/index.ts`. Format numbers/dates/lap times only via `useFormat()` (`src/i18n/format.ts`: French uses a decimal comma, and `parseLocalDate` avoids the UTC off-by-one-day bug for `YYYY-MM-DD` strings). Request errors go through `errorMessage()` (`src/api/errors.ts`), mapping known HTTP statuses to translated text. The dev-only `/styleguide` route shows every component in both themes. The dev frontend container reinstalls npm deps on start (anonymous `node_modules` volume), so a new dependency just needs `docker compose restart frontend`.

**Clubs, coaching & "viewing as"** (frontend): `features/athletes/viewing.ts` holds whose data is shown when it isn't the user's own (per-tab sessionStorage, cleared on logout) and `useActiveAthlete()` returns that athlete — falling back to the user's own if access is lost — so every page must read its athlete through it, never `useMyAthlete`; `components/shell/AthleteSwitcher` + `ViewingBanner` are the UI, fed by the pure `buildSwitchOptions` (me, active coach links, rosters of clubs I administer). Routes: `/club` (list, create, paste an invite), `/club/:id/{members,athletes,invites,tracks,settings}` (tabs per role in `clubs/sections.ts`), `/join#token=…` (`JoinPage`; `ProtectedRoute` keeps path+search+hash in `state.from` so a signed-out invitee returns to the invitation after login/signup — Login/Signup pass it along), `/coach` ("Waiting for you" = link requests + unread comment threads, dashboard cards from `/coach-links/dashboard`, "My coaches"). The Coaching nav item's badge is `useCoachingBadgeCount`. Session comments live in `features/comments` (fifth tab of the session page; showing the thread marks it read). i18n namespaces `club` and `coach`. A bare `form { display: flex; flex-direction: column }` in `index.css` applies to every `<form>`, so a row layout needs an explicit `flex-direction: row`.

Vite + React 19 + TypeScript, feature-folder structure under `src/features/<domain>/` (`api.ts`, `types.ts`, `use<Domain>.ts` hooks using TanStack Query), with route components in `src/routes/`. `src/api/client.ts::apiFetch` is the sole fetch wrapper — it handles the cookie-based auth refresh dance described above; new API calls should go through it rather than raw `fetch`. Routing (`src/App.tsx`) gates everything except `/login` and `/signup` behind `ProtectedRoute`, wrapped in the `AppShell` layout.

## Conventions

- Don't commit `Co-Authored-By: Claude` trailers in git commit messages for this repo.
- `BACKLOG.md` is the maintained backlog (bugs/features/deferred/done) — check it for current priorities and add items there rather than a separate tracker.

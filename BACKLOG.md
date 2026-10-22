# Backlog

## How to use this
- Add new items under the right section, newest on top.
- Check off `[x]` when done, but leave the line — don't delete (keeps history).
- Priority: 🔴 High · 🟡 Medium · 🟢 Low
- Ask Claude Code things like: "add a bug for X", "mark dark mode as done", "what's still open in features?"

---

## 🗺️ Roadmap to v1.0+ (approved 10/19)

Full detail (scope, decisions, verification) lives in the approved plan;
this is the task checklist. Product decisions: mixed power-meter usage
(data-driven + model-based CdA), import = FIT/TCX/GPX + Strava + Intervals.icu,
audience = the club (athletes/coaches/admins), FR+EN UI, deployed on a shared
dedicated OVH VPS for `apex-cycling.net` (changed 10/20 from a shared VPS behind an existing proxy: Caddy now owns 80/443 and gets its own certificate), optional SMTP with copy-link
fallback, mobile-first installable PWA, evolved brand + dark theme.

**Phase 0 — Foundation**
- [x] T0.1 Commit in-progress sqorz ports/DI refactor (step 1); add roadmap here
- [x] T0.2 Mount every backend route under `/api` (client, Vite proxy, Caddyfile)
- [x] T0.3 Vitest + RTL in frontend; CI: `npm test`, ruff, Postgres `alembic upgrade head` job; fix ruff F821s
- [x] T0.4 `.env`-driven dev `docker-compose.yml`

**Phase 1 — Design system & app shell**
- [x] T1.1 Semantic design tokens, light + dark ("night session") themes, fonts, dark wordmark, `/styleguide` — ✋ user checkpoint
- [x] T1.2 Component library (Radix primitives, StatTile, DataTable, Sheet, Toast, ChartFrame…)
- [x] T1.3 i18n FR/EN (i18next, Intl formatting) — infra + auth/shell done; remaining screens' strings are extracted as part of their T1.6 restyle
- [x] T1.4 Responsive AppShell (desktop sidebar, mobile bottom tabs, user menu, new route skeleton)
- [x] T1.5 PWA (manifest, icons, offline shell, install prompt)
- [x] T1.6 Restyle existing screens on the new system (no behavior change)
- [x] T1.7 Redesign the velodrome diagram (real outline, lane markings, clean labels, `velodromeGeometry.ts` tests) — ✋ user checkpoint

**Phase 2 — Athlete profile & account**
- [x] T2.1 Profile fields, dated `athlete_metrics` (weight/FTP/HR), user locale/theme prefs
- [x] T2.2 Change password, password reset (SMTP optional / copy link), delete account, data export
- [x] T2.3 Settings pages (profile, physiology w/ weight chart, preferences, account) — ✋ Phase 2 checkpoint

**Phase 3 — Track analytics on sqorz data**
- [x] T3.1 Effort detection (continuous lap blocks, standing/flying, half-lap pursuit splits)
- [x] T3.2 Multi-lap distances (F200, flying lap, 500m, 750m, 1km, 2/3/4km, custom) — supersedes "Multi-lap custom-distance metric" below
- [x] T3.3 Personal records (computed) + manual results
- [x] T3.4 Session editing (exclude laps, labels, notes, RPE, tags)
- [x] T3.5 Data-driven track settings (length, indoor, elevation, hidden loops/views)
- [x] T3.6 Session detail rework (overview/laps/efforts/notes tabs, checkpoint click → split column) — supersedes "Wire up a click action…" below
- [x] T3.7 Records page + reworked Progress page — ✋ Phase 3 checkpoint

**Phase 4 — Clubs & coaching (M4b)**
- [x] T4.1 Clubs backend (create, members, roles, managed athletes, invite links, club↔sqorz account link)
- [x] T4.2 Coach–athlete links (request/accept/revoke both ways)
- [x] T4.3 Session comments (coach ↔ athlete)
- [x] T4.4 Club pages, athlete switcher, coach dashboard — ✋ Phase 4 checkpoint

**Phase 5 — Production on OVH VPS (v1.0 release)**
Plan changed 10/20: the target is a dedicated bare OVH VPS (domain `apex-cycling.net`; an AWS EC2 variant was built first and the scripts work on any Ubuntu host), so the stack is self-contained (Caddy publishes 80/443 with Let's Encrypt) and Phase 5 includes server installation (`scripts/server-setup.sh`, README guide).
- [x] T5.1 Prod compose for a single host: Caddy on 80/443, uvicorn trusts `X-Forwarded-*` only from the edge network so rate limits key on the real client IP, CSP + security headers, 25 MB `/api` body limit, `no-cache` on `index.html`/`sw.js`/manifest and immutable `/assets` (404s not cached)
- [x] T5.2 Backups: `backup` service (daily `pg_dump` + uploads tarball, 14 daily / 8 weekly, optional sync to any S3-compatible store such as OVH Object Storage), `scripts/restore.sh`, restore drill run for real
- [x] T5.3 `scripts/server-setup.sh` (Docker, ufw + fail2ban, swap, unattended upgrades, log caps), `init-env.sh`, `deploy.sh` (build → pre-deploy backup → `up --wait` → health check → automatic rollback; `--rollback`), `compose.sh`, healthchecks on every service, full `.env.prod.example`, `create-admin` CLI (`python -m app.auth.cli`), README AWS guide, CI `prod-config` job
- [x] T5.4 JSON logs with request id (`X-Request-ID`), deep `/api/health` (503 when DB down), worker heartbeat (`worker_heartbeats` table + file for the container healthcheck), platform-admin page `/admin` (worker status, failed syncs, newest accounts)
- [x] T5.5 First real deploy (https://apex-cycling.net, 10/20) + Playwright smoke suite in `e2e/` (green on the dev stack, a local prod stack and https://apex-cycling.net) — ✋ Phase 5 checkpoint. Still open from the deploy: SMTP and off-host backups (see bugs)

**Phase 6 — Performance tools**
- [x] T6.1 Physics core (Python + TS, shared test vectors) — standing starts model a start-power surge (2× race power until race pace, force-capped), calibrated on real pursuit/kilo first laps
- [x] T6.2 Tools (`/tools`): CdA & power what-if with a sensitivity table, pursuit planner (half-lap schedule, ridden-effort overlay lap by lap, full-screen trackside board at `/tools/pursuit/board` with tap-per-line gaps), gearing, air density; inputs live in the URL ("Copy link"), weight and track pre-filled from the profile — ✋ Phase 6 checkpoint

**Phase 7 — External activities (power/HR/cadence)**
- [x] T7.1 Activities data model (`activities`, `activity_streams`, `activity_power_curves`, migration 0002), compressed streams, uploads storage, Fernet-encrypted connection credentials (`DATA_ENCRYPTION_KEY`, required in `.env.prod` — existing servers must add one before the next deploy; `init-env.sh` generates it for new ones), account export/delete cover activities
- [x] T7.2 FIT/TCX/GPX upload + parsing (`POST /athletes/{id}/activities/upload`, list/get/delete; SHA-256 + same-ride dedupe; originals kept). Parsers were checked against a hand-written FIT encoder and fixtures, **not a real device file** — try one of your own FIT exports before relying on it (open: validate against a real Garmin/Wahoo file)
- [x] T7.3 Metrics engine (MMP, NP/IF/TSS, power/HR zones, CTL/ATL/TSB with sRPE fallback; migration 0003 adds activity `rpe`/`notes`; `training-load` and `power-curve` endpoints, `PATCH` activity; `app.activities.cli recompute-metrics`). Open: zones/stream endpoints for the activity detail come with T7.7
- [x] T7.4 Activity ↔ sqorz session fusion (migration 0004; auto-link on import and after sqorz syncs, sticky manual link/unlink, clock-offset estimate from lap speeds + manual `clock_offset_s`, per-lap and per-effort power/HR/cadence in session detail, linked sessions no longer double-count in the training load). Open: the estimator needs speed variation — a steady-pace session stays at offset 0 until set by hand; validated on synthetic speed traces over real lap times, not a real device file
- [x] T7.5 Intervals.icu sync (migration 0005; API-key connect/status/sync/disconnect endpoints, worker job every 30 min, worker now mounts the uploads volume). Built from the documented API and tested against a fake client and a local stub server — **not yet run against a real Intervals.icu account**; try it with your own key
- [x] T7.6 Strava OAuth sync (OAuth connect/disconnect, token refresh, rate-limit-aware backfill and worker polling, optional webhook with verification; Strava data owner-only, deleted on disconnect/revocation, "View on Strava" `external_url`). **Needs you**: register a Strava API app and set `STRAVA_CLIENT_ID/SECRET` (README); tested against a fake client and `httpx` mock transport, not the live Strava API. T7.7 must show the Strava attribution/link and keep Strava rides out of any shared view (T9.4 leaderboard)
- [x] T7.7 Import hub (drag-and-drop upload with per-file status, Intervals.icu and Strava cards, sync history), Log list + calendar merging sessions and rides, activity page (zoomable multi-channel chart, zones, power curve, session link + clock offset, notes/RPE), `/power` comparison page, fitness/fatigue/form on Home and Progress, per-lap/effort power in the session views, `/streams` and `/analysis` endpoints — ✋ Phase 7 checkpoint. Checked in a browser (light/dark, EN/FR, phone) on seeded data; screenshots not kept. Open: Strava brand assets/"Connect with Strava" button (Strava reviews apps for more than one athlete), an activity-edit audit log, activities in the coach dashboard

**Phase 8 — Aero lab**
- [x] T8.1 CdA/Crr estimation from power + sqorz lap speed (`analysis/aero.py`: per-lap energy balance with the speed change taken from the neighbouring laps, automatic steady-lap pick, CdA+Crr least squares when the laps span ≥ 10 % of speed, else Crr held at the default or a given value; `POST /athletes/{id}/sessions/{event}/aero`, inputs default to the track's air and the profile weight). Checked on synthetic laps and a synthetic FIT recording, **not on a real power file yet**
- [x] T8.2 Aero tests (setup A/B comparison): `aero_tests` (migration 0006) keeps a session, its track, a hand-picked lap list or the automatic pick, the setup (label, position, helmet, skinsuit, bike, notes) and input overrides; CRUD under `/athletes/{id}/aero-tests`, results recomputed on every read (follows lap edits/offsets/weigh-ins, never shows a coach Strava-derived numbers); covered by account export/delete. Plan deviation: results aren't stored
- [x] T8.3 Aero lab UI (`/aero`): session/track pick (sessions with a powered recording; `?session=`, also linked from the session page), CdA/Crr/R²/laps/speed/power tiles, force-vs-speed² scatter with the fit line, lap table with the automatic pick and hand-picking, assumptions form (blank = the default shown), save/edit/delete aero tests, comparison table with a baseline, ΔCdA ("within noise" when inside the combined error) and what it's worth in seconds at a chosen power over 1–4 km (standing start, T6.1 physics) — ✋ Phase 8 checkpoint. Checked in a browser (light/dark, EN/FR, phone) on the real LS-03407 laps with a **synthetic** power recording (CdA 0.245 → estimated 0.238 ± 0.004; 0.241 with Crr fixed at the true value)

**Phase 9 — Equipment, goals, engagement**
- [x] T9.1 Bikes & gears (migration 0007; `bikes` + `gear_setups` (chainring, cog, measured rollout, tire) under `/athletes/{id}/bikes|gears`, a gear assigned to a session (`PUT …/sessions/{event}/gear`) or to one effort (`…/efforts/{first_lap}/gear`, overriding the session's); laps and efforts then carry `est_cadence_rpm` = lap speed ÷ development, the aero lab takes the session bike's weight as its default; `/equipment` page replaces the "coming soon" placeholder; covered by account export/delete). Cadence assumes no coasting (fine on a fixed gear) and needs the track length. Checked in a browser on real LS-03407 laps (EN/FR, light/dark, phone); 50×15 on 2100 mm gives 84 rpm at 25.4 s/250 m, as computed by hand
- [x] T9.1b Saved bikes everywhere a bike counts (migration 0012 `goals.bike_id`): bike-weight picker in the Power/Pursuit tools and saved-gear picker in the Gearing tool (both prefill from the first bike/gear, values go into the URL), bike picker in the aero lab (types its weight, pre-fills the saved test's bike name), optional bike per goal whose weight the prediction uses (else the CdA test's bike weight); deleting a bike detaches it from goals; a planned effort can name the gear to ride it in (in the targets JSON, no migration)
- [x] T9.2 Goals (migration 0008; `goals` = event + start + optional track + target time + date, CRUD under `/athletes/{id}/goals`; the best so far, gap, progress (from the best when the goal was set) and days left are computed on every read; a predicted time simulates the event (T6.1 physics) at the best average power over the duration nearest the target (power curve of the last 120 days) with the CdA of the newest saved aero test, and says what is missing (`no_cda`, `no_power`, `no_weight`, `no_track[_length]`) when it can't; Goals card on Home, EN/FR). The prediction is an estimate (road/trainer power and position-dependent CdA), validated against the physics only, not against a real ride
- [x] T9.3 Planned sessions (migration 0009; `planned_sessions` = date + title + description + planned efforts (label, reps, optional standard event/start/target time), `/athletes/{id}/planned-sessions` CRUD; the coach, a club admin or the athlete plans; the author and the athlete's side edit or delete, **only the athlete's side** (`speaks_for_athlete`) marks it done/skipped or links it to the sqorz session ridden (`PUT/DELETE …/session`; linking = done, anything but done unlinks); chips on the Log calendar (dashed, filled when done), a "Planned sessions" card on Home and a "Plan a session" button on the Log, EN/FR). A coach plans by switching to the athlete in the athlete switcher. Open: no email/in-app notification when a plan is added (see the coaching-notifications feature), and plans don't yet show on the coach dashboard
- [x] T9.4 Opt-in club leaderboard (migration 0010; `Athlete.leaderboard_club_id` = the club the athlete agreed to appear on, so opting in lapses the moment they leave or change club; `GET /clubs/{id}/leaderboard?event_key&track_id[&start_type&sex&category]` for any club member: best time per opted-in athlete on one of the club's tracks, ranks shared on ties, age categories present for the filter; Leaderboard tab in the club, Privacy tab in Settings. Only the athlete (or a club admin for a managed athlete) may opt in: a coach or club admin who can otherwise edit the profile gets 403). Times come from `personal_records` (sqorz laps) and manual results with a track, never Strava) — ✋ Phase 9 checkpoint. Checked in a browser on a seeded club (opt-in via the UI, a private athlete stays off the board, EN light desktop, FR dark phone); screenshots not kept. Open: per-club leaderboards need the club linked to a sqorz facility (an admin task today); a leaderboard of power (W/kg) would have to stay Strava-free the same way

---

## 🐛 Bugs

- [ ] 🟡 Production runs without off-host backups or SMTP — *added 10/20*
  - Why: decided at first-deploy planning to start with neither. Backups exist only on the VPS disk (`/var/backups/apex-cycling`), so losing the server loses them; password resets and club invites go through admin-copied links.
  - Notes: off-host = OVH VPS backup option or `BACKUP_S3_*` in `.env.prod` (README "Backups and restore"); email = `SMTP_*` in `.env.prod`. Revisit once real club data is in.

## ✨ Features

- [ ] 🟡 Email notifications for coaching — *added 10/19*
  - Why: a coach–athlete request, or a new comment on a session, only shows up in the in-app "Waiting for you" list and the nav badge. With SMTP configured (`app/core/mail.py`) it could also email.
  - Notes: reuse `send_email` the way club invites do; needs a per-user opt-out first.

- [ ] 🟢 Coach dashboard "form" is recent load only — *added 10/19*
  - Why: the cards show sessions, laps and mean RPE for the last 7 days against the 7 before. A real fitness/fatigue/form model (CTL/ATL/TSB) needs power or HR data, which arrives with the import phases.
  - Notes: `app/athletes/dashboard.py` is the one place to extend.

- [ ] 🟡 Refactoring of backend — *added 7/28*
  - Why: Backend business logic is tightly coupled to the database layer. Which make maintenance and testting difficult.
  - Notes: Adding manual dependency injection. Use of the repository pattern and DTO

- [ ] 🟢 Same-named tracks on the records board — *added 10/19*
  - Why: sqorz re-creates the Bromont track under new ids (the LS-03407 export has several "Tour complet"), so the board can list the same place name twice, and records don't carry over between the copies.
  - Notes: needs a way to merge tracks (T3.5 track settings is the natural home); distinct ids are kept apart on purpose until then.

## 🗺️ Deferred to v2+

- [ ] 🟢 Training-plan recommendations — *added 7/23*
  - Notes: additive module over existing fact tables.

- [ ] 🟢 Celery/Redis for background jobs — *added 7/23*
  - Notes: only if APScheduler's simplicity stops being enough.

- [ ] 🟢 TimescaleDB — *added 7/23*
  - Notes: only if plain-Postgres progression queries get slow.

## ✅ Done
- [x] Roster API doesn't return the UCI category — *added 10/19, resolved 10/22 (`RosterAthlete.category`, as of today; the club roster page has a Category column and an age-category filter)*
- [x] One club per athlete profile — *added 10/19, resolved 10/22 (migration 0015: `athletes.club_id` → `athlete_clubs` roster table with the leaderboard consent per club; managed athletes stay on one club; TSS timezone = club joined first)*
- [x] Long lap tables on phones — *added 10/19, resolved 10/22 (phones show the first 12 laps with a "Show all N laps" toggle; CSV and desktop untouched)*
- [x] Frontend test suite times out under CPU load — *added 10/20, fixed 10/21*
- [x] M4b — Roster management + coach dashboard — *added 7/23, resolved 10/19 (Phase 4, T4.1–T4.4)*
- [x] Fuller `.env`-based config for dev compose — *resolved 10/19 (T0.4)* — *added 7/23*
- [x] Multi-lap custom-distance metric (e.g. pursuit "fastest 4km" spanning ~16 laps) — *added 7/24 (scoped out during M3), resolved 10/19 (T3.2)*
- [x] Wire up a click action for track-diagram checkpoint flags — *added 7/24, resolved 10/19 (T3.6: highlights the split column)*
- [x] M1 — Auth, identity/tenancy models, base SPA, docker-compose — *done 7/23*
- [x] M2 — Sqorz connections + ingestion pipeline + APScheduler worker — *done 7/23*
- [x] M3 — Training data normalization + session/progression endpoints — *done 7/23*
- [x] M4a — SPA charts (sessions list/detail, progression) — *done 7/23*
- [x] M5 — Polish & deploy prep (prod Docker images, Caddy, CI) — *done 7/23*
- [x] Post-M3 schema change — per-athlete private training data copies — *done 7/24*
- [x] Track sensor schema + SVG track diagram + dashboard sidebar shell — *done 7/24*
- [x] Rename project from Track Trainer to ApexCycling — *done 7/27*
- [x] Validate the sqorz response schema — *added 7/23, resolved 7/29*
- [x] Dev Postgres volume orphaned by the Track Trainer → ApexCycling rename — *added 7/27, resolved 7/29*
- [x] "Keep me logged in" login option — *added 7/23, resolved 7/29*
- [x] 🟢 Prod Let's Encrypt issuance never verified against a real domain — *added 7/27*
---

## Item template (copy when adding new)

- [ ] 🟡 Title — *added MM/DD*
  - Details / repro / notes

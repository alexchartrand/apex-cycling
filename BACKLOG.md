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

- [x] 🔴 Aero fit accepts a non-positive CdA on the fixed-Crr path — *added 10/22 (from REVIEW-2026-10-21), fixed 10/22 (`PLAUSIBLE_CDA` = (0, 1.0] m²; otherwise no fit and the new `implausible_fit` problem, EN/FR)*
  - Why: with Crr held fixed, `analysis/aero.py::estimate` never checks the CdA it fits, so messy laps give CdA ≤ 0 and the goal prediction answers 143 km/h or a 500.
  - Notes: reject an implausible fit (CdA ≤ 0 or > 1.0) so the goal prediction degrades to `no_cda`; tests in `tests/test_aero.py`.

- [ ] 🟡 Production runs without off-host backups or SMTP — *added 10/20*
  - Why: decided at first-deploy planning to start with neither. Backups exist only on the VPS disk (`/var/backups/apex-cycling`), so losing the server loses them; password resets and club invites go through admin-copied links.
  - Notes: off-host = OVH VPS backup option or `BACKUP_S3_*` in `.env.prod` (deploy.md "Backups and restore"); email = `SMTP_*` in `.env.prod`. Revisit once real club data is in.

## ✨ Features

**Suggestions of 10/22** (audit of UX, analytics and backend after v1; grouped in the suggested order — A foundations, B alive, C analysis, D coach & season)

- [~] 🔴 A1 Sqorz polls re-normalize the whole history every time — *added 10/22; skip-when-unchanged done 10/22 (migration 0016, `NORMALIZER_VERSION`, "Sync now" forces); still open: retention and bulk lap upserts*
  - Why: every poll (20 min per active transponder) re-normalizes the full payload and recomputes records even when nothing changed (`ingestion/sqorz/service.py`), and the normalizer costs several round trips per lap; `get_latest_hash` loads the whole JSON payload to read a hash; `ingestion_runs`/`raw_snapshots` grow forever.
  - Notes: done — skip when the hash is unchanged, no assignment changed since `normalized_at` and the normalizer version matches; `get_latest_hash` selects only the hash. Open: retention for `ingestion_runs`/`raw_snapshots` (deletes data, so decide the policy first — e.g. keep the newest few snapshots per transponder and runs for 90 days; the Import page's sync history reads runs), and upserting laps in bulk in `normalizer.py` (still several round trips per lap whenever the payload does change).
  - Still missing (10/23 review):
    - **Retention policy not decided, no code yet.** Nothing prunes `ingestion_runs`/`raw_snapshots` (no job in `jobs.py`/`runner.py`). Constraints: always keep the newest snapshot per `external_ref` (it is the baseline for the hash comparison), pruning runs shortens the Import page's sync history, and the job belongs in the worker (`runner.py`), not the request path. Test it against the fake ports/an in-memory DB.
    - **Bulk lap upserts**: the per-lap loop in `normalizer.py` (`for lap_payload in member.get("trainingLaps")`) does its own queries per lap.
    - **A changed payload still re-reads the whole history** (and recomputes records for every affected athlete): bulk upserts make laps cheaper but not proportional to what changed. Decide whether to normalize only new/changed sessions or accept it.
    - **No success criterion**: add a target (e.g. round trips per sync, or a query-count test on a fixture with a typical history) so "done" can be checked.
    - **Tests for the skip** (hash unchanged / assignment edited since `normalized_at` / `NORMALIZER_VERSION` bump / `force`) should be confirmed in `test_sqorz_ingestion_service.py`.
    - **Priority**: the main fix is in; consider dropping to 🟡 or splitting retention and bulk upserts into two entries.
- [ ] 🔴 A2 Alerting when the worker or syncs fail — *added 10/22*
  - Why: failures only reach the logs and `/admin`; no backoff or failure count per connection; `restart: unless-stopped` never restarts an *unhealthy* worker.
  - Notes: consecutive-failure count + backoff, email/ntfy to platform admins, healthcheck-driven restart, external uptime monitor on `/api/health`.
- [x] 🟡 A3 Missing composite indexes — *added 10/22, done 10/22 (migration 0017: training_events, activities, ingestion_runs, raw_snapshots, personal_records; the unindexed FKs on aero_tests/goals/planned_sessions were left out on purpose — tiny tables, only hit by bike/track deletes)*
  - Notes: `training_events(athlete_id, event_date)`, `activities(athlete_id, start_time)`, `ingestion_runs(data_source_connection_id, requested_at)`, `raw_snapshots(external_ref, fetched_at)`, `personal_records(track_id, event_key, start_type)`, FKs `aero_tests.track_id`, `goals.track_id/bike_id`, `planned_sessions.training_event_id`.
- [x] 🟡 A4 Frontend ships as one big chunk and refetches on every focus — *added 10/22, done 10/22 (every page behind `React.lazy` with a skeleton fallback in the shell, entry chunk 241 KB; `staleTime` 60 s)*
  - Notes: `React.lazy` per route in `App.tsx`; default `staleTime` (~60 s) in `main.tsx`.
- [ ] 🟡 A5 Slow read paths — *added 10/22; training-load horizon, goals CdA and dashboard batching done 10/23*
  - Notes: goals fit every aero test (decoding streams) to use the newest (`goals/service.py`); coach dashboard N+1 (last session, failing transponders, load, plans, goal and race per athlete — still several queries per athlete, sequential); `/sessions` and `/progression` unpaginated. Done: `training_load` only reads activities/rated sessions from 252 days (6 × the CTL constant) before the window, so it no longer scans the whole history (older load is under 0.25 % of the curve). Goals now stop at the newest aero test with a fit (`aero.service.newest_fitted_test`) instead of fitting every test. The coach dashboard fetches last session, failing transponders (latest run per connection), plans, goals and next race for all athletes in one query each; only `training_load` and the records board (for athletes with goals) remain per athlete. `GET /athletes/{id}/sessions` takes optional `from` / `to` / `limit` (defaults unchanged; `/progression` already filters by `from` / `to` in SQL) and Home fetches only the last two weeks plus its 5 newest (`useSessionsRange`). Open: Log (month-based fetch for the calendar, load-more for the list) and the session pickers (Compare, Aero, Pursuit, plan link, sqorz sync check) still load the whole list; per-athlete `training_load` on the coach dashboard.
- [x] 🟡 B1 Session insights & PR moments — *added 10/22, done 10/23 (`training/insights.py` pure + `insights_service.py`; `GET /athletes/{id}/insights` and `…/sessions/{event}/insights`; computed on read like the record history, no table)*
  - Done: personal records (with the round time they broke — "first time under 1:10"), season bests (calendar year, needs an earlier result that season), best Nth lap of the season (efforts of ≥ 4 laps, the biggest improvement per session and track), most consistent effort (lap-time spread, comparable lap counts). A first result is never a "record". Banner on the session page, "What's new" card on Home (30 days, 3 sessions, 4 each), toast after "Sync now".
  - Open: insights are sqorz-only (manual results don't count); they load every lap of the athlete on each read, like the record history — fold them into A5's slow-path work if it shows.
- [x] 🟢 B2 Share card for a PR or effort — *added 10/22, done 10/23 (`features/share/`: canvas drawing, `navigator.share` with files, falls back to saving the PNG)*
  - Done: a share button on each record badge (session overview) and on each effort card: 1080×1350 dark card with the velodrome, the time, the gain over the previous best, and lap bars. Sqorz data only, so Strava-free. Checked in a browser (desktop download of the real PNG); the phone share sheet itself wasn't exercised.
- [x] 🟡 B3 Notifications (in-app centre, Web Push, email) — *added 10/22, done 10/23 (migration 0018; `app/notifications/`)*
  - Done: a bell (sidebar, phone top bar) with unread count and panel; events new record (once per session, ≤ 5 listed, last 7 days only), comment (athlete, active coaches and people already in the thread, never the author), coaching request, plan added by someone else, sync failed (once per streak, not for "Sync now"). Per-user, per-event opt-outs for bell/push/email (Settings → Notifications; new records don't email by default). The row is also the outbox: the worker sends push (VAPID, `pywebpush`) and email every minute. Push and email are off until `VAPID_*` / `SMTP_*` are set (deploy.md "Optional integrations"); covered by account export and deletion. Absorbs "Email notifications for coaching".
  - Open: "sync stalled" (worker hung / no successful run for a day) belongs with A2 alerting; coaches aren't told about their athletes' records; no retry for a failed email or push (marked delivered either way); push untested against a real push service.
- [x] 🟡 B4 First-run checklist — *added 10/22, done 10/23 (`features/onboarding/`)*
  - Done: Home checklist "2 of 4" (transponder, weight, club and coach optional), hideable per browser, never shown when viewing another athlete; `/import#sqorz` scrolls to the sqorz card; "Where do I find the code?" help; after adding a transponder or "Sync now" the card says "Found N laps in M sessions" or that none have arrived yet. Manual syncs now refresh the session list and records (staleTime had hidden them for 60 s).
- [x] 🟡 C1 Compare sessions and efforts — *added 10/22, done 10/23 (`features/compare/`, route `/compare?a=&ae=&b=&be=`)*
  - Done: pick two efforts, from one session or two (session select + effort select per side; an effort is named in the URL by its first lap id, the longest one is the default). A figures table (time, best lap, speeds, spread, fade, power, HR; better figure in bold, B − A), a lap-by-lap overlay, the running gap and the half-lap splits side by side. A compare button on every effort card starts it.
  - Open: no session-level view (it is always efforts; pick the effort you mean); the Log and session header have no entry point yet; not checked in a browser.
- [x] 🟡 C2 Pacing analysis per effort — *added 10/22, done 10/23 (`training/pacing.py` pure; `EffortDetail.pacing`)*
  - Done: lap-time spread (CV), fade (last third vs first), every lap's deviation from the even pace, shown as tiles and a bar chart on the effort card. The reference laps are the finished, non-excluded ones minus a standing start's first lap.
  - Open: deviation from a *pursuit schedule* isn't on the effort card (it needs a rider setup and a target); the Pursuit tool already lays an effort over its schedule (`effortElapsedByLap`).
- [x] 🟢 C3 Planned vs actual per planned effort — *added 10/22, done 10/23 (`planning/matching.py` pure, `planning/comparison.py`; `GET …/planned-sessions/{id}/comparison`)*
  - Done: the plan's targets expand into reps in plan order and each takes the first later effort that has a result for its event and start (a warm-up or a failed effort is passed over); hit / miss with the gap to the target, "ridden" when the plan gave no time, "not ridden", "not measured" for a block with no event. "How it went" section in the plan dialog once a session is linked (409 before).
  - Open: one effort answers one rep (an effort holding several reps back to back isn't split); the flying-lap events use the session's best window of that effort, not a chosen lap.
- [x] 🟢 C4 Sprint metrics from segment times — *added 10/22, done 10/23 (`training/sprint.py` pure; `EffortDetail.peak_speed_kmh / launch_*`)*
  - Done: top speed = the fastest stretch (≥ 20 m) between two placed checkpoints of a non-excluded lap; launch = time to the first placed checkpoint of a standing start, with the average acceleration from rest (2·d/t²). Gates are placed by the loop's `distance_m` when sqorz sent one, else by name: `NNNm` = distance left to the finish, `Finish` = the line (the real LS-03407 export has no distances). The launch needs the track length.
  - Open: the launch assumes the lap timer starts at the gate, and peak speed is an average over ≥ 20 m, not an instantaneous one; none of it checked against a real standing-start session.
- [x] 🟡 D1 Coach dashboard v2 — *added 10/22, done 10/23 (`athletes/dashboard.py`, `athletes/squad.py`; `GET /coach-links/squad`)*
  - Done: each athlete card also shows fitness/fatigue/form (CTL/ATL/TSB as the coach sees it, so no Strava), how much of the last 28 days' plans were followed (done / done + skipped + unanswered) with what is coming up, the nearest open goal with its progress bar, and the next race with the taper. A "Squad" tab ranks every actively coached athlete by their best at one event, start and (optionally) track — sqorz laps and hand-entered results only, equal times share a rank, athletes without a time are listed last. Supersedes "Coach dashboard form is recent load only".
  - Open: the dashboard still does a few queries per athlete (A5); plans don't notify the coach when missed; the squad has no sex/category filter yet.
- [x] 🟢 D2 Seasons, competitions, ICS feed — *added 10/22, done 10/23 (migration 0019; `app/seasons/`, `/season` page)*
  - Done: a session can be marked as a race (Notes tab; badge in the Log; `training_events.is_race`, never written by sync). Races (`competitions`: name, date, A/B/C priority, place, notes, optional goal) with a days-to-go countdown and a taper (A 10 days, B 5, C none) — a "Next race" card on Home. Seasons are just start dates (a season lasts until the next starts); each shows its sessions, races and the best per place/event/start against the best before the season began (`improved`). Phone calendar: a secret `/api/calendar/<token>.ics` link (only the hash is stored, shown once, replace or turn off; only the athlete or a club admin for a managed athlete) with the athlete's non-skipped plans (targets in the description), races and the taper start, as all-day events.
  - Open: no race entry on the Log calendar; the ICS has no time of day (plans have none); a race isn't linked to its session beyond "same day"; coaches can add races for an athlete but can't open the calendar link.
- [x] 🟢 D3 CP/W′ and FTP suggestion from the power curve — *added 10/22, done 10/23 (`analysis/critical_power.py` pure; `GET /athletes/{id}/power-profile?days=`; card on `/power`)*
  - Done: two-parameter CP fit (least squares of work on time) over the best efforts of 3–20 minutes in the last 90 days — it needs one effort of 6 min or less and one of 12 min or more, else no fit; and "your data suggests FTP ≈ X" = 95 % of the best 20 minutes, offered only when it differs from the FTP in force by more than 2 % ("Set FTP to X W" records it as today's FTP; "Not now" is remembered per rider and value).
  - Open: the 95 % rule is the usual field-test rule, not a physiological test; CP isn't used for zones or the goal prediction.
- [ ] 🟢 Smaller suggestions — *added 10/22*
  - Pursuit board: works offline cold (precache inputs), landscape allowed (manifest locks portrait), vibrate on tap, confirm Reset/undo.
  - Wellness check-in (sleep, soreness, optional HRV) next to RPE; conditions-adjusted times (air density, weather for outdoor tracks).
  - Chart data-table fallbacks for screen readers (LapChart, CurveChart, RecordTimeline, Progress); a real 404 page; Import/Progress reachable from the phone tabs.

- [x] 🟡 Email notifications for coaching — *added 10/19, done 10/23 (part of B3: coaching requests and comments email when SMTP is set, per-user opt-out)*

- [x] 🟢 Coach dashboard "form" is recent load only — *added 10/19, resolved 10/23 (D1: the cards carry CTL/ATL/TSB)*
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

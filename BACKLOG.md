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
OVH VPS behind an existing reverse proxy, optional SMTP with copy-link
fallback, mobile-first installable PWA, evolved brand + dark theme.

**Phase 0 — Foundation**
- [x] T0.1 Commit in-progress sqorz ports/DI refactor (step 1); add roadmap here
- [x] T0.2 Mount every backend route under `/api` (client, Vite proxy, Caddyfile)
- [x] T0.3 Vitest + RTL in frontend; CI: `npm test`, ruff, Postgres `alembic upgrade head` job; fix ruff F821s
- [x] T0.4 `.env`-driven dev `docker-compose.yml`

**Phase 1 — Design system & app shell**
- [x] T1.1 Semantic design tokens, light + dark ("night session") themes, fonts, dark wordmark, `/styleguide` — ✋ user checkpoint
- [x] T1.2 Component library (Radix primitives, StatTile, DataTable, Sheet, Toast, ChartFrame…)
- [ ] T1.3 i18n FR/EN (i18next, Intl formatting, all strings extracted)
- [ ] T1.4 Responsive AppShell (desktop sidebar, mobile bottom tabs, user menu, new route skeleton)
- [ ] T1.5 PWA (manifest, icons, offline shell, install prompt)
- [ ] T1.6 Restyle existing screens on the new system (no behavior change)
- [ ] T1.7 Redesign the velodrome diagram (real outline, lane markings, clean labels, `velodromeGeometry.ts` tests) — ✋ user checkpoint

**Phase 2 — Athlete profile & account**
- [ ] T2.1 Profile fields, dated `athlete_metrics` (weight/FTP/HR), user locale/theme prefs
- [ ] T2.2 Change password, password reset (SMTP optional / copy link), delete account, data export
- [ ] T2.3 Settings pages

**Phase 3 — Track analytics on sqorz data**
- [ ] T3.1 Effort detection (continuous lap blocks, standing/flying, half-lap pursuit splits)
- [ ] T3.2 Multi-lap distances (F200, flying lap, 500m, 750m, 1km, 2/3/4km, custom) — supersedes "Multi-lap custom-distance metric" below
- [ ] T3.3 Personal records (computed) + manual results
- [ ] T3.4 Session editing (exclude laps, labels, notes, RPE, tags)
- [ ] T3.5 Data-driven track settings (length, indoor, elevation, hidden loops/views)
- [ ] T3.6 Session detail rework (overview/laps/efforts/notes tabs, checkpoint click → split column) — supersedes "Wire up a click action…" below
- [ ] T3.7 Records page + reworked Progress page

**Phase 4 — Clubs & coaching (M4b)**
- [ ] T4.1 Clubs backend (create, members, roles, managed athletes, invite links, club↔sqorz account link)
- [ ] T4.2 Coach–athlete links (request/accept/revoke both ways)
- [ ] T4.3 Session comments (coach ↔ athlete)
- [ ] T4.4 Club pages, athlete switcher, coach dashboard

**Phase 5 — Production on OVH (v1.0 release)**
- [ ] T5.1 Prod compose for shared host (loopback port, proxy headers, real-IP rate limiting, security headers)
- [ ] T5.2 Backups (daily pg_dump + uploads, rotation, restore drill)
- [ ] T5.3 Deploy script, log rotation, healthchecks, full `.env.prod.example`, `create-admin` CLI, OVH guide
- [ ] T5.4 Structured logs, deep health, worker heartbeat, platform-admin page
- [ ] T5.5 Playwright e2e smoke suite — ✋ first deploy with user

**Phase 6 — Performance tools**
- [ ] T6.1 Physics core (Python + TS, shared test vectors)
- [ ] T6.2 Tools: air density, CdA/power what-if, pursuit planner + trackside board, gear calculator

**Phase 7 — External activities (power/HR/cadence)**
- [ ] T7.1 Activities data model, compressed streams, encrypted credentials
- [ ] T7.2 FIT/TCX/GPX upload + parsing
- [ ] T7.3 Metrics engine (MMP, NP/IF/TSS, CTL/ATL/TSB with sRPE fallback)
- [ ] T7.4 Activity ↔ sqorz session fusion (per-lap power/HR/cadence)
- [ ] T7.5 Intervals.icu sync
- [ ] T7.6 Strava OAuth sync (Strava data visible to owner only, per Strava API terms)
- [ ] T7.7 Import hub, Log/calendar, activity detail, power curve, fitness chart

**Phase 8 — Aero lab**
- [ ] T8.1 CdA/Crr estimation from power + sqorz lap speed
- [ ] T8.2 Aero tests (setup A/B comparison)
- [ ] T8.3 Aero lab UI

**Phase 9 — Equipment, goals, engagement**
- [ ] T9.1 Bikes & gears (estimated cadence) — supersedes "Gear/bike setup tracking" below
- [ ] T9.2 Goals
- [ ] T9.3 Coach planned sessions
- [ ] T9.4 Opt-in club leaderboard

---

## 🐛 Bugs

- [ ] 🟢 Prod Let's Encrypt issuance never verified against a real domain — *added 7/27*
  - Repro: `docker-compose.prod.yml` + Caddy has only been run with `localhost` (self-signed cert). A real public DNS record pointed at a host, confirming Caddy actually obtains a Let's Encrypt cert, hasn't been done.
  - Notes: see README.md "Not yet exercised for real"; low risk until an actual prod domain is in play.

## ✨ Features

- [ ] 🔴 M4b — Roster management + coach dashboard — *added 7/23*
  - Why: last remaining v1 milestone. `app/clubs/` currently has only `models.py` — no router/schemas/service exist yet.
  - Notes: needs club creation (who becomes `club_admin` of a brand-new club — unresolved by the original plan), an invite mechanism for club membership + coach-athlete linking (no email infra in this stack — likely a shareable link/token, not real email sending), club-admin roster screens, and a coach dashboard (roster + recent-session glance).

- [ ] 🟡 Refactoring of backend — *added 7/28*
  - Why: Backend business logic is tightly coupled to the database layer. Which make maintenance and testting difficult.
  - Notes: Adding manual dependency injection. Use of the repository pattern and DTO

- [x] 🟡 Fuller `.env`-based config for dev compose — *resolved 10/19 (T0.4)* — *added 7/23*
  - Why: `backend/app/core/config.py` already supports `.env` via pydantic-settings, but `docker-compose.yml` still hardcodes Postgres user/password/db name and `CORS_ORIGINS` inline instead of sourcing from `.env`.
  - Notes: dev-only risk today, but worth cleaning up before it's copy-pasted into a real deployment.

- [ ] 🟢 Multi-lap custom-distance metric (e.g. pursuit "fastest 4km" spanning ~16 laps) — *added 7/24 (scoped out during M3)*
  - Why: `find_best_distance_window` in `app/training/service.py` is deliberately scoped to a single lap's segments — sqorz never reports a track's total circuit length, so there's no reliable way to carry cumulative distance across a lap boundary.
  - Notes: revisit if per-checkpoint `distance_m` data turns out to be reliably populated for a target track. Deliberate scope call, not an oversight.

- [ ] 🟢 Wire up a click action for track-diagram checkpoint flags — *added 7/24*
  - Why: `TrackSchema.tsx` flags already highlight on hover and toggle a local "selected" visual state on click, but no action is wired to that click yet.
  - Notes: explicitly deferred by the user as future work when the diagram was built.

## 🗺️ Deferred to v2+

- [ ] 🟢 Strava/Garmin ingestion — *added 7/23*
  - Notes: own fact table; OAuth on `data_source_connections`, which already has an unused encrypted `credentials` column for this.

- [ ] 🟢 Training-plan recommendations — *added 7/23*
  - Notes: additive module over existing fact tables.

- [ ] 🟢 Gear/bike setup tracking — *added 7/23*
  - Notes: future `gears` table, nullable FK from laps later.

- [ ] 🟢 Celery/Redis for background jobs — *added 7/23*
  - Notes: only if APScheduler's simplicity stops being enough.

- [ ] 🟢 TimescaleDB — *added 7/23*
  - Notes: only if plain-Postgres progression queries get slow.

## ✅ Done

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
---

## Item template (copy when adding new)

- [ ] 🟡 Title — *added MM/DD*
  - Details / repro / notes

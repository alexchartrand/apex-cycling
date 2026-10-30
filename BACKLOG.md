# Backlog

## How to use this
- Add new items under the right section, newest on top.
- When an item is done, move it to ✅ Done as a single line (title + dates); open follow-ups go to their own open item.
- Priority: 🔴 High · 🟡 Medium · 🟢 Low
- Ask Claude Code things like: "add a bug for X", "mark dark mode as done", "what's still open in features?"

---

## 🐛 Bugs

- [ ] 🟡 Production runs without off-host backups — *added 10/20 (SMTP part done 10/23: Resend)*
  - Why: backups exist only on the VPS disk (`/var/backups/apex-cycling`), so losing the server loses them.
  - Notes: OVH VPS backup option or `BACKUP_S3_*` in `.env.prod` (deploy.md "Backups and restore"). Revisit once real club data is in.

## ✨ Features

- [~] 🟡 Sprint W — Workout builder & library — *added 10/30; spec agreed with the user; W1 done 10/30 (migration 0020)*
  - Why: plans are free-form today (`PlannedEffort` targets) and nothing reaches a head unit or trainer. Workouts should be bike-generic (power/cadence on a trainer or the road) with track-specific steps (laps/meters, standing/flying start), sent to devices and scored afterwards.
  - **Model**: a `Workout` = name, description, tags, `steps` JSON tree: steps (kind warmup/work/recovery/cooldown, free text) and repeat blocks **nested one level** (e.g. 3 × [4 × (flying 200, 3 laps easy)], 10 min between sets). Step length: time, **or distance in m / laps** (laps × track `length_m`; a lap step on a track without a length has no distance), **or open** (lap button). Targets, any of: power (% FTP or W, single or range), cadence range, RPE/free text. A track step can also carry a standard `event_key` + `start_type` (as `PlannedEffort` does today) and an optional `target_time_ms` and gear — as teeth (`GearRatio`), not a `gear_setup_id`, since a library workout belongs to no athlete; scheduling (W4) maps it to the athlete's matching gear. HR targets are left out on purpose. Derived on read: estimated duration, TSS, and an intensity profile.
  - **Library & permissions**: owner = an athlete (personal) or a coach (coach library); built-in presets come from a hand-maintained, bilingual `workouts/presets.json` (FR/EN names and descriptions, loaded like `facilities.json`). Athletes browse their own, presets and **the full library of every active coach**; only the owner edits. Tags + search/filter (type, duration, track vs generic); "Duplicate" copies any visible workout into my library.
  - **Scheduling**: scheduling a workout creates a `PlannedSession` holding a **snapshot** (`PlannedSession.workout` JSON + nullable `source_workout_id`), so library edits never rewrite assigned/past plans; that copy can be tweaked on the plan. Same rules as T9.3 (anyone with `require_athlete_access` plans; only the athlete's side marks done/links). The plan dialog's targets editor is replaced by the workout editor; existing `targets` stay readable and keep comparing (no migration).
  - **Editor**: visual blocks (add/reorder steps, repeat blocks) + a live intensity chart, estimated duration/TSS. Track steps are drawn by estimated duration.
  - **Exports** (download): `.fit` workout (lap-button/distance steps, step notes such as "Flying 200 – 50×15 – 11.2 s"), `.zwo` (stays in % FTP, since Zwift applies its own FTP), `.erg`/`.mrc`. Watts use the FTP in force on the planned date (library export: today). A track step on a trainer format becomes a free-ride/max block with an **estimated duration**: target time, else the athlete's best at that event, else `physics.simulate` at defaults.
  - **Intervals.icu push**: per-athlete opt-in on the existing connection; every scheduled workout is created on their Intervals.icu calendar, and edit/reschedule/delete/skip updates or removes it there (store the remote event id on the plan; only ever touch events we created). Intervals.icu then forwards to Garmin/Wahoo/Zwift. Done by the worker with retries, never inline. Verify the events API (workout as file vs native text) against the live docs before building.
  - **Printable card**: canvas PNG like the share card (`features/share/`), phone-lock-screen/stem sized: steps, laps, targets in W/time, gear.
  - **Compliance**: extend planned-vs-actual (`planning/matching.py`, `comparison.py`): track steps → sqorz efforts (time vs target, as today); power steps → the linked recording (mean power/cadence per step window, via `visible_conditions`, so Strava stays out for coaches).
  - **Housekeeping**: workouts are in account export and deletion (`build_export`, `delete_athlete`/`delete_account`; a coach deleting their account keeps the athletes' snapshots), new i18n namespace `workouts`, migration with clean `alembic check`.
  - Tasks:
    - ~~W1 Model + schemas + step tree validation + derived duration/TSS (pure, tested), CRUD + library visibility rules.~~ Done: `app/workouts/`, `/api/workouts` (+ `/estimate` compute-only for the editor, `/{id}/duplicate`). Watt targets count as unrated in the library (no FTP there); presets (W2) aren't in the list yet.
    - W2 Presets file (Claude drafts ~10–15 classic track + generic sessions, the user reviews).
    - W3 Library page + visual editor + intensity chart.
    - W4 Scheduling: snapshot on `PlannedSession`, plan dialog uses the editor.
    - W5 Exporters `.fit` / `.zwo` / `.erg` / `.mrc` (pure, tested; `.fit` checked with `fitdecode` round-trip) + track-step duration estimate.
    - W6 Intervals.icu push (opt-in, worker outbox, update/delete sync).
    - W7 Printable card PNG.
    - W8 Compliance for power steps + workout-aware matching.
  - Out of scope v1: Garmin Connect / Wahoo / TrainingPeaks direct push (partner approval), importing .zwo/.fit, club libraries, HR targets, trackside board mode.

- [~] 🔴 A1 Sqorz polls re-normalize the whole history every time — *added 10/22; skip-when-unchanged done 10/22 (migration 0016, `NORMALIZER_VERSION`, "Sync now" forces); still open: retention and bulk lap upserts*
  - Why: whenever the payload changes, the normalizer re-reads the full history at several round trips per lap and recomputes records; `ingestion_runs`/`raw_snapshots` grow forever.
  - **Retention policy not decided, no code yet.** Nothing prunes `ingestion_runs`/`raw_snapshots`. Constraints: always keep the newest snapshot per `external_ref` (baseline for the hash comparison), pruning runs shortens the Import page's sync history, and the job belongs in the worker (`runner.py`). E.g. keep the newest few snapshots per transponder and runs for 90 days.
  - **Bulk lap upserts**: the per-lap loop in `normalizer.py` (`for lap_payload in member.get("trainingLaps")`) does its own queries per lap.
  - **A changed payload still re-reads the whole history**: decide whether to normalize only new/changed sessions or accept it.
  - **No success criterion**: add a target (e.g. a query-count test on a fixture with a typical history).
  - **Priority**: the main fix is in; consider dropping to 🟡 or splitting retention and bulk upserts into two entries.
- [ ] 🔴 A2 Alerting when the worker or syncs fail — *added 10/22*
  - Why: failures only reach the logs and `/admin` (and the athlete's bell, B3); no backoff or failure count per connection; `restart: unless-stopped` never restarts an *unhealthy* worker.
  - Notes: consecutive-failure count + backoff, email/ntfy to platform admins, "sync stalled" (no successful run for a day), healthcheck-driven restart, external uptime monitor on `/api/health`.
- [~] 🟡 A5 Slow read paths — *added 10/22; training-load horizon, goals CdA, dashboard batching and Home session range done 10/23*
  - Open: Log (month-based fetch for the calendar, load-more for the list) and the session pickers (Compare, Aero, Pursuit, plan link, sqorz sync check) still load the whole session list; per-athlete `training_load` and records board on the coach dashboard; insights load every lap of the athlete on each read.
- [ ] 🟡 Validate imports and estimates against real data — *added 10/26 (collected from T7.2–T8.1, C4)*
  - A real Garmin/Wahoo FIT file (parsers only checked against a hand-written encoder); a real Intervals.icu key; a live Strava app (`STRAVA_CLIENT_ID/SECRET`); the aero fit and clock-offset estimate on a real power recording; sprint launch/top speed on a real standing-start session; Web Push against a real push service.
- [ ] 🟢 Follow-ups from shipped features — *added 10/26 (collected from the done items)*
  - Activities: Strava brand assets / "Connect with Strava" button (needed before Strava approves more than one athlete); activity-edit audit log; a steady-pace session's clock offset stays 0 until set by hand.
  - Notifications: coaches aren't told about their athletes' records or missed plans; no retry for a failed email/push (marked delivered either way).
  - Insights: manual results don't count.
  - Compare: no session-level view; no entry point from the Log or session header; not checked in a browser (nor Sprint C/D in general).
  - Pacing: deviation from a pursuit schedule on the effort card.
  - Planned vs actual: an effort holding several reps isn't split.
  - Squad: no sex/category filter.
  - Seasons: races not on the Log calendar; ICS has no time of day; a race isn't linked to its session beyond "same day"; coaches can't open the calendar link.
  - CP isn't used for zones or the goal prediction.
  - Leaderboard: needs the club linked to a sqorz facility (platform-admin task today); a W/kg board would have to stay Strava-free.
- [ ] 🟢 Smaller suggestions — *added 10/22*
  - Pursuit board: works offline cold (precache inputs), landscape allowed (manifest locks portrait), vibrate on tap, confirm Reset/undo.
  - Wellness check-in (sleep, soreness, optional HRV) next to RPE; conditions-adjusted times (air density, weather for outdoor tracks).
  - Chart data-table fallbacks for screen readers (LapChart, CurveChart, RecordTimeline, Progress); a real 404 page; Import/Progress reachable from the phone tabs.

- [ ] 🟡 Refactoring of backend — *added 7/28*
  - Why: Backend business logic is tightly coupled to the database layer, which makes maintenance and testing difficult.
  - Notes: manual dependency injection, repository pattern and DTOs. Sqorz client+service (step 1) and the Intervals/Strava sync are done in that shape; next is `ingestion/sqorz/normalizer.py` (step 2).

- [ ] 🟢 Same-named tracks on the records board — *added 10/19*
  - Why: sqorz re-creates a track under new ids (the LS-03407 export has two "Tour complet"), so pickers and the board can list the same place twice, and records don't carry over between the copies.
  - Notes: needs a way to merge tracks (track settings is the natural home); distinct ids are kept apart on purpose until then.

## 🗺️ Deferred to v2+

- [ ] 🟢 Training-plan recommendations — *added 7/23*
  - Notes: additive module over existing fact tables.

- [ ] 🟢 Celery/Redis for background jobs — *added 7/23*
  - Notes: only if APScheduler's simplicity stops being enough.

- [ ] 🟢 TimescaleDB — *added 7/23*
  - Notes: only if plain-Postgres progression queries get slow.

## ✅ Done
- [x] Coaching rework: per-athlete summary + read-only coach view (`/coach/athletes/:id`), coaches limited to comments and plans (`require_athlete_editor`), no more "view as" for coaches — *added 10/30, done 10/30*
- [x] D3 CP/W′ and FTP suggestion from the power curve — *added 10/22, done 10/23*
- [x] D2 Seasons, competitions, ICS calendar feed (migration 0019) — *added 10/22, done 10/23*
- [x] D1 Coach dashboard v2 (form, plan compliance, goal, next race) + squad ranking — *added 10/22, done 10/23*
- [x] C4 Sprint metrics from segment times (top speed, launch) — *added 10/22, done 10/23*
- [x] C3 Planned vs actual per planned effort — *added 10/22, done 10/23*
- [x] C2 Pacing analysis per effort — *added 10/22, done 10/23*
- [x] C1 Compare sessions and efforts (`/compare`) — *added 10/22, done 10/23*
- [x] B4 First-run checklist — *added 10/22, done 10/23*
- [x] B3 Notifications: bell, Web Push, email (migration 0018) — *added 10/22, done 10/23*
- [x] B2 Share card for a PR or effort — *added 10/22, done 10/23*
- [x] B1 Session insights & PR moments — *added 10/22, done 10/23*
- [x] Email notifications for coaching — *added 10/19, done 10/23 (part of B3)*
- [x] Coach dashboard "form" is recent load only — *added 10/19, resolved 10/23 (D1)*
- [x] Production SMTP (Resend) — *added 10/20, done 10/23*
- [x] A4 Lazy-loaded routes + 60 s query `staleTime` — *added 10/22, done 10/22*
- [x] A3 Missing composite indexes (migration 0017) — *added 10/22, done 10/22*
- [x] Aero fit accepts a non-positive CdA on the fixed-Crr path — *added 10/22, fixed 10/22*
- [x] Roster API doesn't return the UCI category — *added 10/19, resolved 10/22*
- [x] One club per athlete profile (migration 0015, `athlete_clubs`) — *added 10/19, resolved 10/22*
- [x] Long lap tables on phones — *added 10/19, resolved 10/22*
- [x] Frontend test suite times out under CPU load — *added 10/20, fixed 10/21*
- [x] Phase 9 — Equipment, goals, engagement: T9.1 bikes & gears, T9.1b saved bikes everywhere, T9.2 goals, T9.3 planned sessions, T9.4 opt-in club leaderboard — *done 10/20*
- [x] Phase 8 — Aero lab: T8.1 CdA/Crr estimation, T8.2 aero tests, T8.3 `/aero` UI — *done 10/20*
- [x] Phase 7 — External activities: T7.1 data model, T7.2 FIT/TCX/GPX upload, T7.3 metrics engine, T7.4 sqorz fusion, T7.5 Intervals.icu, T7.6 Strava, T7.7 import hub/log/activity pages — *done 10/20*
- [x] Phase 6 — Performance tools: T6.1 physics core, T6.2 `/tools` + trackside board — *done 10/20*
- [x] Phase 5 — Production on OVH VPS: T5.1 prod compose, T5.2 backups, T5.3 server/deploy scripts, T5.4 logs/health/admin, T5.5 first deploy + e2e — *done 10/20*
- [x] Phase 4 — Clubs & coaching (M4b): T4.1 clubs, T4.2 coach links, T4.3 comments, T4.4 club pages/switcher/dashboard — *done 10/19*
- [x] Phase 3 — Track analytics: T3.1 efforts, T3.2 multi-lap distances, T3.3 records, T3.4 session editing, T3.5 track settings, T3.6 session detail, T3.7 records/progress pages — *done 10/19*
- [x] Phase 2 — Athlete profile & account: T2.1 profile/metrics, T2.2 password/export/delete, T2.3 settings pages — *done 10/19*
- [x] Phase 1 — Design system & app shell: T1.1 tokens/themes, T1.2 components, T1.3 i18n, T1.4 AppShell, T1.5 PWA, T1.6 restyle, T1.7 velodrome diagram — *done 10/19*
- [x] Phase 0 — Foundation: T0.1 sqorz refactor step 1, T0.2 `/api` prefix, T0.3 Vitest + CI, T0.4 `.env` dev compose — *done 10/19*
- [x] M4b — Roster management + coach dashboard — *added 7/23, resolved 10/19 (Phase 4)*
- [x] Fuller `.env`-based config for dev compose — *added 7/23, resolved 10/19 (T0.4)*
- [x] Multi-lap custom-distance metric — *added 7/24, resolved 10/19 (T3.2)*
- [x] Click action for track-diagram checkpoint flags — *added 7/24, resolved 10/19 (T3.6)*
- [x] Validate the sqorz response schema — *added 7/23, resolved 7/29*
- [x] Dev Postgres volume orphaned by the Track Trainer → ApexCycling rename — *added 7/27, resolved 7/29*
- [x] "Keep me logged in" login option — *added 7/23, resolved 7/29*
- [x] Prod Let's Encrypt issuance verified against a real domain — *added 7/27, resolved 10/20 (T5.5)*
- [x] Rename project from Track Trainer to ApexCycling — *done 7/27*
- [x] Post-M3 schema change — per-athlete private training data copies — *done 7/24*
- [x] Track sensor schema + SVG track diagram + dashboard sidebar shell — *done 7/24*
- [x] M1–M5 — Auth/tenancy, sqorz ingestion + worker, normalization, SPA charts, prod images/Caddy/CI — *done 7/23*
---

## Item template (copy when adding new)

- [ ] 🟡 Title — *added MM/DD*
  - Details / repro / notes

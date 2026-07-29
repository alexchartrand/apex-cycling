# Backlog

## How to use this
- Add new items under the right section, newest on top.
- Check off `[x]` when done, but leave the line — don't delete (keeps history).
- Priority: 🔴 High · 🟡 Medium · 🟢 Low
- Ask Claude Code things like: "add a bug for X", "mark dark mode as done", "what's still open in features?"

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

- [ ] 🟡 Fuller `.env`-based config for dev compose — *added 7/23*
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

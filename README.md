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

## Production deployment (OVH VPS)

The prod stack (`docker-compose.prod.yml`) is meant for **one bare Linux
server with nothing else on it** — here an OVH VPS serving
`apex-cycling.net` — running five containers.

| Service | Role |
| --- | --- |
| `frontend` | [Caddy](https://caddyserver.com/): owns ports 80/443, gets and renews its own Let's Encrypt certificate, serves the built SPA, proxies `/api` to the backend, sets the security headers |
| `backend` | FastAPI behind Caddy (private network only), runs migrations on start |
| `worker` | background sqorz poller |
| `db` | Postgres 16 (named volume) |
| `backup` | daily `pg_dump` + uploads archive with rotation |

Only Caddy is reachable from outside. Everything is operated with the scripts
in `scripts/`. The same steps work on any Ubuntu VPS or cloud instance.

### 1. Order the server and point the domain at it

1. **Order the VPS** in the OVH manager: pick a datacenter close to the club
   (Beauharnois, Québec for CNCB) and **Ubuntu 24.04** as the image. Add your
   SSH public key at order time if offered. OVH emails the server's IPv4 address
   and the login user (usually `ubuntu`, with `sudo`).
2. **DNS**: create an **`A` record** for `apex-cycling.net` pointing at the
   server's IPv4 address (OVH manager → Web Cloud → Domain names → DNS zone, or
   at your registrar if the zone is elsewhere). **Do not create an `AAAA`
   record**: the stack only listens on IPv4 (Docker's IPv6 proxy hides client
   addresses, which would break per-user rate limiting), and Let's Encrypt
   prefers IPv6 when a record exists. Wait until `dig +short apex-cycling.net`
   returns the IP before the first deploy.
3. OVH's optional network firewall is not needed; the server runs its own
   (`ufw`, set up below).

### 2. Prepare the server (once)

```bash
ssh ubuntu@apex-cycling.net
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/alexchartrand/apex-cycling.git
cd apex-cycling                  # a private repo needs a deploy key or token for the clone
sudo scripts/server-setup.sh     # Docker, firewall, fail2ban, swap, updates, log rotation
exit                             # log back in so the docker group applies
```

`server-setup.sh` is idempotent: Docker Engine + Compose plugin from Docker's
apt repo, `ufw` (SSH, 80, 443 only) and `fail2ban`, unattended security
upgrades, a 2 GB swap file if there is none, a 10 MB × 5 log cap for every
container, and `/var/backups/apex-cycling` for backups. SSH stays open to any address (your home IP changes), guarded by `fail2ban`.
Once you have confirmed that logging in with your SSH key works, run
`sudo scripts/server-setup.sh --ssh-key-only` to turn off password logins
(it refuses if no key is installed); keep your first session open until a
second one connects.

### 3. Configure and deploy

```bash
ssh ubuntu@apex-cycling.net
cd apex-cycling
scripts/init-env.sh apex-cycling.net alexchartrand91@gmail.com   # writes .env.prod with fresh secrets
$EDITOR .env.prod        # optional: SMTP, timezone, backup settings (documented inline)
scripts/deploy.sh
```

`init-env.sh` also generates `DATA_ENCRYPTION_KEY`, which encrypts the Strava
tokens and Intervals.icu keys stored in the database. **Upgrading a server
whose `.env.prod` predates this key:** `deploy.sh` stops with "set
DATA_ENCRYPTION_KEY" until you add one. Do it once, before the deploy:

```bash
echo "DATA_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr + - | tr / _)" >> .env.prod
```

Keep a copy of `.env.prod` with your backups: restoring a database onto a
server with a different key leaves those connections unreadable (athletes would
have to reconnect them). Don't change the key later; to rotate it, put the new
key first and keep the old one after a comma (`new,old`).

`deploy.sh` builds the images (tagged with the git commit), takes a backup if
a database already exists, starts everything, waits for every container's
healthcheck, then checks `https://<domain>/api/health` through Caddy. If the
new version doesn't come up healthy it puts the previous images back by
itself. First start takes a few minutes (image builds on a small instance,
then the certificate).

Create the first platform admin (can edit any track's settings and open the
Administration page from the account menu):

```bash
scripts/compose.sh exec backend python -m app.auth.cli create-admin you@example.com "Your Name"
```

Open `https://apex-cycling.net` and sign up the club's people, or create a club
and send invite links.

### 4. Day to day

| Task | Command |
| --- | --- |
| Deploy the latest `master` | `scripts/deploy.sh` |
| Go back to the previous version | `scripts/deploy.sh --rollback` (migrations are not undone) |
| Status / logs | `scripts/compose.sh ps` · `scripts/compose.sh logs -f backend` |
| Password-reset link (no SMTP) | `scripts/compose.sh exec backend python -m app.auth.cli reset-link <email>` |
| Make someone platform admin | `scripts/compose.sh exec backend python -m app.auth.cli grant-admin <email>` |
| Worker / failed syncs / new accounts | Administration page in the app |

Use `scripts/compose.sh` rather than plain `docker compose`: it points at the
images `deploy.sh` last deployed. Backend and worker logs are JSON, one object
per line, each request tagged with a `request_id` that is also returned in the
`X-Request-ID` response header.

### 5. Backups and restore

The `backup` service writes to `/var/backups/apex-cycling` at 03:00
(`BACKUP_HOUR`, container `TZ`): `daily/` keeps 14 days, `weekly/` the Sunday
backup for 8 weeks; each is a `pg_dump` custom-format file plus a tarball of
the uploads volume. The directory is root-owned, so use `sudo` to look at it.

Restore (replaces **all** current data):

```bash
sudo ls /var/backups/apex-cycling/daily
sudo scripts/restore.sh latest                                    # newest daily backup
sudo scripts/restore.sh /var/backups/apex-cycling/weekly/apex-20261018-030000.dump \
                        /var/backups/apex-cycling/weekly/uploads-20261018-030000.tar.gz
```

The backup holds third-party credentials (Strava tokens, Intervals.icu keys)
encrypted with `DATA_ENCRYPTION_KEY` from `.env.prod`. Keep a copy of that file
with the backups: restoring onto a server with a different key still works, but
those connections can no longer be read and users have to reconnect them.

This was drilled for real: back up, change data, restore, confirm the old data
is back and the newer changes are gone. Repeat the drill after changing the
backup setup.

**Off-host copy.** Backups on the server's own disk don't survive losing the
server, so keep a second copy elsewhere. Either enable OVH's VPS backup option,
or let the backup service sync to any S3-compatible store. With OVH Object
Storage: create a container (bucket) and an S3 user with read/write access, then
add to `.env.prod` (endpoint and region as shown for your container in the OVH
manager):

```
BACKUP_S3_URI=s3://<bucket>/apex-cycling
BACKUP_S3_ENDPOINT=https://s3.<region>.io.cloud.ovh.net
BACKUP_S3_REGION=<region>
BACKUP_S3_ACCESS_KEY=…
BACKUP_S3_SECRET_KEY=…
```

then `scripts/deploy.sh`. Backblaze B2 or AWS S3 work the same way (leave the
endpoint empty for AWS S3). The sync mirrors the local rotation, so the remote
copy keeps the same 14 daily / 8 weekly set. Check the first night's run with
`sudo ls /var/backups/apex-cycling` and the bucket's contents.

### Connecting rides (optional)

Athletes can bring rides in by uploading FIT/TCX/GPX files (nothing to set up),
by connecting **Intervals.icu** with their API key (nothing to set up on the
server either), or by connecting **Strava**, which needs an application of
your own: create one at <https://www.strava.com/settings/api> with your domain
as "Authorization Callback Domain", then put `STRAVA_CLIENT_ID` and
`STRAVA_CLIENT_SECRET` in `.env.prod` (the callback is
`https://<domain>/api/strava/callback`). Until Strava approves the application
it accepts one connected athlete. Strava rides are visible only to the athlete
who connected them (Strava's terms) and are deleted when they disconnect. For
instant imports instead of polling every 3 hours, see the webhook notes in
`.env.prod.example`. `DATA_ENCRYPTION_KEY` (generated by `init-env.sh`)
protects the stored keys and tokens; an existing `.env.prod` from before this
feature needs one added (`openssl rand -base64 32 | tr + - | tr / _`).

### Notifications (optional)

The bell in the app (new records, comments, coaching requests, planned
sessions, failed syncs) needs nothing. Two more channels are opt-in per
person in Settings → Notifications and need the server set up:

- **Email** — the same `SMTP_*` settings as password resets. The worker sends
  it, so it also needs them (the compose files pass them).
- **Push** (a notification on the phone or computer even when the app is
  closed) — make a VAPID key pair once with
  `scripts/compose.sh exec backend python -m app.notifications.cli generate-vapid`
  and put `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT`
  (`mailto:you@example.com`) in `.env.prod`. Each browser then turns push on
  for itself. On an iPhone the app has to be added to the home screen first.
  Changing the key pair later silently stops existing subscriptions; people
  turn push off and on again.

### 6. Troubleshooting

- **No certificate / browser shows a TLS error**: `scripts/compose.sh logs frontend`.
  Almost always DNS not pointing at the server yet, a stray `AAAA` record, or
  ports 80/443 blocked (check `sudo ufw status` and OVH's firewall, if enabled).
- **Locked out of SSH**: use the OVH manager's KVM/VNC console to log in and
  fix `ufw`/`fail2ban` (`sudo fail2ban-client status sshd`, `sudo ufw status`).
- **Build killed or very slow**: out of memory; check `free -h` shows swap, or
  choose a larger VPS.
- **A deploy says unhealthy**: `scripts/compose.sh ps` and
  `scripts/compose.sh logs backend`; the previous version was already restored.
- **Rate limits seem shared between users**: the `client_ip` field in the
  backend's logs should be each visitor's real address, not `172.28.0.1`.
- **Moving to a new server**: set it up as above, copy a backup over, and run
  `scripts/restore.sh` before pointing DNS at it.

### Smoke-testing the prod stack on your own machine

```bash
scripts/init-env.sh localhost you@example.com
printf 'HSTS_MAX_AGE=0\nHTTP_PORT=8080\nHTTPS_PORT=8443\nBACKUP_DIR=/tmp/apex-backups\n' >> .env.prod
mkdir -p /tmp/apex-backups
scripts/deploy.sh --no-pull        # https://localhost:8443, self-signed certificate
```

`DOMAIN=localhost` makes Caddy use its own private CA, so the browser warns.
Tear down with `scripts/compose.sh down -v`.

### Smoke tests against a running deployment

`e2e/` is a small Playwright suite that works against any base URL: health
endpoint, security/caching headers (with `E2E_EDGE=1`, prod edge only), then a
full journey (redirect when signed out, wrong password, sign up, main pages,
reload, log out/in, delete the account) that fails on any console error, CSP
violation or 5xx. It deletes the account it creates, so it is safe against
production. Signup and login are rate limited per IP, so don't loop it.

```bash
cd e2e && npm install && npx playwright install chromium   # once
E2E_BASE_URL=https://apex-cycling.net E2E_EDGE=1 npm test    # production
E2E_BASE_URL=https://localhost:8443  E2E_EDGE=1 npm test    # local prod stack
npm test                                                     # dev stack (:5173)
```

### Not yet exercised

Issuing a real Let's Encrypt certificate for a public domain, sending real
SMTP mail, and the S3 sync against OVH Object Storage itself (it is verified
against a local S3-compatible server) have only been verified on paper. The
first real deploy (roadmap T5.5) is where all three get confirmed.

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

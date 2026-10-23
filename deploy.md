# Deploying ApexCycling

The prod stack (`docker-compose.prod.yml`) is meant for **one bare Linux
server with nothing else on it** — here an OVH VPS serving
`apex-cycling.net` — running five containers.

| Service | Role |
| --- | --- |
| `frontend` | [Caddy](https://caddyserver.com/): owns ports 80/443, gets and renews its own Let's Encrypt certificate, serves the built SPA, proxies `/api` to the backend, sets the security headers |
| `backend` | FastAPI behind Caddy (private network only), runs migrations on start |
| `worker` | background sqorz / Intervals.icu / Strava poller, notification sender |
| `db` | Postgres 16 (named volume) |
| `backup` | daily `pg_dump` + uploads archive with rotation |

Only Caddy is reachable from outside. Everything is operated with the scripts
in `scripts/`, run from the checkout at `/opt/apex-cycling` on the server.
The same steps work on any Ubuntu VPS or cloud instance.

Day to day this is just [Releasing a new version](#releasing-a-new-version).

---

## Releasing a new version

Versions are git tags of the form `vMAJOR.MINOR.PATCH` (annotated, on
`master`). The tag is the human name for what is running; the images are still
tagged with the commit (`APP_TAG`, kept in `.deployed-tag`), so the two always
map: `git describe --tags` on the server shows which release the checkout is.

| Bump | When |
| --- | --- |
| `PATCH` (`v1.0.1`) | bug fixes, copy changes, no new feature |
| `MINOR` (`v1.1.0`) | new feature or sprint, new migration, new optional env var |
| `MAJOR` (`v2.0.0`) | breaking change: a required new env var, a data migration that can't be reverted, a dropped feature |

### 1. Before you tag (dev machine)

```bash
git switch master && git pull --ff-only
git status                           # must be clean
```

- [ ] **CI is green on `master`** (GitHub → Actions): ruff, pytest, the Postgres
      migration round-trip + `alembic check`, frontend lint/test/build, prod-config.
      Or locally: `cd backend && python -m pytest && ruff check .`, then
      `cd frontend && npm run lint && npm test && npm run build`.
- [ ] **New migration?** It must be in CI's `upgrade head → check → downgrade base → upgrade head`
      round-trip. Rollback does **not** undo migrations, so look at whether the
      previous version still runs on the new schema.
- [ ] **New required env var?** Add it to `.env.prod.example` and to `.env.prod`
      **on the server before deploying**, or `deploy.sh` / the containers refuse to
      start. Optional vars can wait.
- [ ] **Docs/backlog updated** (`BACKLOG.md`, `CLAUDE.md` if the architecture changed).

### 2. Tag and push

```bash
git tag -l 'v*' --sort=-v:refname | head -3      # last version(s)
git tag -a v1.1.0 -m "v1.1.0: <one line: what's in it>"
git push origin master
git push origin v1.1.0
```

Push the tag by name rather than `--tags`, so stray local tags don't go up.
If you tagged the wrong commit and **haven't deployed it**: `git tag -d v1.1.0`
and `git push origin :refs/tags/v1.1.0`, then retag. Once deployed, don't move a
tag — cut a new patch version instead.

Optionally publish release notes on GitHub:
`gh release create v1.1.0 --title "v1.1.0" --generate-notes`.

### 3. Deploy (server)

```bash
ssh ubuntu@apex-cycling.net
cd /opt/apex-cycling
git fetch --tags
git log -1 --oneline origin/master               # is this the commit you tagged?
scripts/deploy.sh
git describe --tags                              # → v1.1.0
```

`deploy.sh` does `git pull --ff-only`, builds the images (tagged with the
commit), takes a **pre-deploy backup** if a database already exists, starts
everything, waits for every container's healthcheck, then checks
`https://<domain>/api/health` through Caddy. If the new version doesn't come up
healthy it puts the previous images back by itself and exits non-zero.

If `master` has moved past your tag since you tagged (someone pushed another
commit), `git describe --tags` shows `v1.1.0-2-g…` — you deployed more than the
tag. Either deploy the tag exactly (`git checkout v1.1.0 && scripts/deploy.sh --no-pull`,
then `git switch master` so the next `deploy.sh` can pull again), or tag the new head.

### 4. Verify

```bash
scripts/compose.sh ps                            # every service healthy
scripts/compose.sh logs --since 5m backend worker
cat .deployed-tag .previous-tag                  # what's running, what rollback would use
```

From your dev machine, the browser smoke test (signs up an account and deletes it;
signup/login are rate limited per IP, so don't loop it):

```bash
cd e2e && E2E_BASE_URL=https://apex-cycling.net E2E_EDGE=1 npm test
```

Then open the app and click through what changed. Check the Administration page:
the worker heartbeat should be fresh and no connection should show a failed sync.

### 5. If it went wrong

| Situation | Action |
| --- | --- |
| `deploy.sh` reported unhealthy | Already rolled back to the previous images. Read `scripts/compose.sh logs backend`, fix, release a new patch version. |
| Deployed fine, but it's broken | `scripts/deploy.sh --rollback` (back to the previous images, a few seconds). Migrations are **not** undone. |
| A migration damaged data | `sudo scripts/restore.sh latest` — the pre-deploy backup is the newest one. Replaces **all** data since. Then roll back the images. |
| Need an older release, not just the previous one | `git checkout v1.0.0 && scripts/deploy.sh --no-pull`, then `git switch master`. |

After a rollback, leave the bad tag in place (it was deployed, it is history),
fix forward, and cut the next patch version. Note the bad release in `BACKLOG.md`
if the cause isn't obvious from the fix.

### Quick reference (a routine release)

```bash
# dev machine
git switch master && git pull --ff-only && git status
git tag -a vX.Y.Z -m "vX.Y.Z: <summary>" && git push origin master vX.Y.Z

# server
ssh ubuntu@apex-cycling.net 'cd /opt/apex-cycling && git fetch --tags && scripts/deploy.sh && git describe --tags'

# dev machine
cd e2e && E2E_BASE_URL=https://apex-cycling.net E2E_EDGE=1 npm test
```

---

## Day to day

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

## Backups and restore

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

then `scripts/deploy.sh --no-pull`. Backblaze B2 or AWS S3 work the same way
(leave the endpoint empty for AWS S3). The sync mirrors the local rotation, so
the remote copy keeps the same 14 daily / 8 weekly set. Check the first night's
run with `sudo ls /var/backups/apex-cycling` and the bucket's contents.

## Optional integrations

### Connecting rides

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

### Notifications

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

## Troubleshooting

- **No certificate / browser shows a TLS error**: `scripts/compose.sh logs frontend`.
  Almost always DNS not pointing at the server yet, a stray `AAAA` record, or
  ports 80/443 blocked (check `sudo ufw status` and OVH's firewall, if enabled).
- **Locked out of SSH**: use the OVH manager's KVM/VNC console to log in and
  fix `ufw`/`fail2ban` (`sudo fail2ban-client status sshd`, `sudo ufw status`).
- **Build killed or very slow**: out of memory; check `free -h` shows swap, or
  choose a larger VPS.
- **A deploy says unhealthy**: `scripts/compose.sh ps` and
  `scripts/compose.sh logs backend`; the previous version was already restored.
- **`git pull --ff-only` fails in deploy.sh**: the server checkout is on a
  detached tag or has local commits. `git switch master`, then deploy again.
- **Rate limits seem shared between users**: the `client_ip` field in the
  backend's logs should be each visitor's real address, not `172.28.0.1`.
- **Moving to a new server**: order an Ubuntu 24.04 VPS, clone the repo to `/opt/apex-cycling`, run
  `sudo scripts/server-setup.sh` and `scripts/init-env.sh` (copy the old
  `DATA_ENCRYPTION_KEY` into `.env.prod`), copy a backup over and run
  `scripts/restore.sh`, then deploy and point the DNS `A` record (no `AAAA`) at it.

## Smoke-testing the prod stack on your own machine

```bash
scripts/init-env.sh localhost you@example.com
printf 'HSTS_MAX_AGE=0\nHTTP_PORT=8080\nHTTPS_PORT=8443\nBACKUP_DIR=/tmp/apex-backups\n' >> .env.prod
mkdir -p /tmp/apex-backups
scripts/deploy.sh --no-pull        # https://localhost:8443, self-signed certificate
```

`DOMAIN=localhost` makes Caddy use its own private CA, so the browser warns.
Tear down with `scripts/compose.sh down -v`.

## Smoke tests against a running deployment

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

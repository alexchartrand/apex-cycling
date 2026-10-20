#!/bin/bash
# Deploy the checked-out code to this server: pull, build, back up, start,
# verify, and roll back to the previous images if the new ones don't come up.
#
#   scripts/deploy.sh              git pull --ff-only, then deploy
#   scripts/deploy.sh --no-pull    deploy the working tree as it is
#   scripts/deploy.sh --rollback   go back to the previously deployed images
#
# Images are tagged with the git commit (APP_TAG), so a rollback is just
# `up` with the previous tag. Database migrations are NOT undone by a
# rollback; if a bad migration ran, use scripts/restore.sh with the backup
# this script takes right before deploying.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env.prod ] || { echo "missing .env.prod — run scripts/init-env.sh first" >&2; exit 1; }
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)
IMAGES=(apex-cycling-backend apex-cycling-worker apex-cycling-frontend apex-cycling-backup)
KEEP_TAGS=4

set -a; . ./.env.prod; set +a
DOMAIN=${DOMAIN:-localhost}

check_health() {
  local curl_args=(-fsS --max-time 10 --resolve "$DOMAIN:${HTTPS_PORT:-443}:127.0.0.1")
  # The localhost smoke-test certificate comes from Caddy's private CA.
  [ "$DOMAIN" = localhost ] && curl_args+=(-k)
  curl "${curl_args[@]}" "https://$DOMAIN:${HTTPS_PORT:-443}/api/health" >/dev/null
}

bring_up() {
  "${COMPOSE[@]}" up -d --remove-orphans --wait --wait-timeout 300 && check_health
}

previous=$(cat .deployed-tag 2>/dev/null || true)

if [ "${1:-}" = --rollback ]; then
  prev_file=.previous-tag
  [ -f "$prev_file" ] || { echo "no previous deployment recorded" >&2; exit 1; }
  target=$(cat "$prev_file")
  echo "==> Rolling back to $target"
  export APP_TAG=$target
  bring_up
  echo "$previous" > "$prev_file"
  echo "$target" > .deployed-tag
  echo "Rolled back to $target (database migrations were not reverted)."
  exit 0
fi

if [ "${1:-}" != --no-pull ]; then
  echo "==> git pull"
  git pull --ff-only
fi

export APP_TAG
APP_TAG=$(git rev-parse --short=10 HEAD)
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  # Unique per set of local changes, so a rollback target is never overwritten.
  APP_TAG="$APP_TAG-dirty-$(git diff HEAD | sha1sum | cut -c1-6)"
fi
echo "==> Deploying $APP_TAG (currently: ${previous:-nothing})"

echo "==> Build"
"${COMPOSE[@]}" build

if [ -n "$("${COMPOSE[@]}" ps --status running --quiet db)" ]; then
  echo "==> Pre-deploy backup"
  "${COMPOSE[@]}" run --rm --no-deps backup once
fi

echo "==> Start"
if bring_up; then
  [ -n "$previous" ] && [ "$previous" != "$APP_TAG" ] && echo "$previous" > .previous-tag
  echo "$APP_TAG" > .deployed-tag
  echo "==> Deployed $APP_TAG at https://$DOMAIN"
else
  echo "!! $APP_TAG did not become healthy" >&2
  "${COMPOSE[@]}" ps >&2 || true
  if [ -n "$previous" ] && [ "$previous" != "$APP_TAG" ]; then
    echo "==> Rolling back to $previous" >&2
    export APP_TAG=$previous
    if bring_up; then
      echo "Rolled back to $previous. Migrations from the failed deploy may remain; see scripts/restore.sh." >&2
    else
      echo "!! Rollback failed too — check: ${COMPOSE[*]} logs" >&2
    fi
  fi
  exit 1
fi

echo "==> Pruning old images (keeping the newest $KEEP_TAGS tags)"
for image in "${IMAGES[@]}"; do
  docker images --format '{{.Tag}}' "$image" | grep -vx -e latest -e "$APP_TAG" -e "${previous:-none}" \
    | tail -n +"$KEEP_TAGS" | xargs -r -I{} docker rmi "$image:{}" >/dev/null 2>&1 || true
done
docker image prune -f >/dev/null

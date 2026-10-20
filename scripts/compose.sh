#!/bin/bash
# `docker compose` for the prod stack, pointed at the currently deployed images:
#
#   scripts/compose.sh ps
#   scripts/compose.sh logs -f backend
#   scripts/compose.sh exec backend python -m app.auth.cli create-admin you@example.com "Your Name"
#
# Plain `docker compose -f docker-compose.prod.yml …` would pick the `latest`
# tag instead of the commit scripts/deploy.sh deployed.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env.prod ] || { echo "missing .env.prod — run scripts/init-env.sh first" >&2; exit 1; }
if [ -f .deployed-tag ]; then
  export APP_TAG
  APP_TAG=$(cat .deployed-tag)
fi
exec docker compose -f docker-compose.prod.yml --env-file .env.prod "$@"

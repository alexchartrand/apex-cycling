#!/bin/bash
# Restore a backup made by the backup service into the running prod stack.
#
#   scripts/restore.sh <apex-….dump> [uploads-….tar.gz]
#   scripts/restore.sh latest             newest daily dump (+ its uploads)
#
# The database is DROPPED and recreated, so this replaces everything. Run from
# the repo root on the server. Pass --yes to skip the confirmation.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(scripts/compose.sh)
BACKUP_DIR=${BACKUP_DIR:-/var/backups/apex-cycling}

assume_yes=0
args=()
for a in "$@"; do
  if [ "$a" = "--yes" ]; then assume_yes=1; else args+=("$a"); fi
done
[ ${#args[@]} -ge 1 ] || { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

dump=${args[0]}
uploads=${args[1]:-}
if [ "$dump" = latest ]; then
  dump=$(ls -1t "$BACKUP_DIR"/daily/apex-*.dump | head -n1)
  uploads=$(ls -1t "$BACKUP_DIR"/daily/uploads-*.tar.gz 2>/dev/null | head -n1 || true)
fi
[ -f "$dump" ] || { echo "no such dump: $dump" >&2; exit 1; }

# shellcheck disable=SC1091
set -a; . ./.env.prod; set +a
DB_USER=${POSTGRES_USER:-apex_cycling}
DB_NAME=${POSTGRES_DB:-apex_cycling}

echo "Restoring database '$DB_NAME' from $dump"
[ -n "$uploads" ] && echo "and uploads from $uploads"
if [ "$assume_yes" -ne 1 ]; then
  read -r -p "This replaces ALL current data. Type 'restore' to continue: " answer
  [ "$answer" = restore ] || { echo "aborted"; exit 1; }
fi

echo "Stopping app services…"
"${COMPOSE[@]}" stop frontend worker backend
"${COMPOSE[@]}" up -d db --wait

echo "Recreating database…"
"${COMPOSE[@]}" exec -T db psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"$DB_NAME\" WITH (FORCE)" \
  -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\""

echo "Loading dump…"
"${COMPOSE[@]}" exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --exit-on-error < "$dump"

if [ -n "$uploads" ] && [ -f "$uploads" ]; then
  echo "Restoring uploads…"
  # Project name is fixed in docker-compose.prod.yml, so the volume name is too.
  uploads_volume=apex-cycling-prod_uploads
  docker run --rm -v "$uploads_volume":/data -v "$(readlink -f "$uploads")":/in.tar.gz:ro alpine \
    sh -c 'rm -rf /data/* /data/.[!.]* 2>/dev/null; tar -xzf /in.tar.gz -C /data'
fi

echo "Starting the stack…"
"${COMPOSE[@]}" up -d --wait
echo "Restore complete."

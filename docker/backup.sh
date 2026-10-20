#!/bin/bash
# Backups for the prod stack. PG* env vars point at the db service.
#
#   backup.sh daemon   run forever: one backup a day at BACKUP_HOUR (container TZ)
#   backup.sh once     one backup now (scripts/deploy.sh runs this before a deploy)
#
# Layout under /backups:
#   daily/apex-<stamp>.dump          pg_dump custom format (pg_restore)
#   daily/uploads-<stamp>.tar.gz     the uploads volume
#   weekly/…                         the Sunday backup, kept longer
#   last-success                     touched after every good run (healthcheck)
set -euo pipefail

BACKUP_ROOT=${BACKUP_ROOT:-/backups}
UPLOADS_DIR=${UPLOADS_DIR:-/data/uploads}
KEEP_DAILY=${BACKUP_KEEP_DAILY:-14}
KEEP_WEEKLY=${BACKUP_KEEP_WEEKLY:-8}
HOUR=${BACKUP_HOUR:-3}

log() { echo "$(date -u +%FT%TZ) backup: $*"; }

# keep_newest <dir> <glob-prefix> <count>: delete all but the newest <count>.
prune() {
  local dir=$1 prefix=$2 keep=$3
  # ls fails when nothing matches yet (first run); that is fine.
  # shellcheck disable=SC2012
  { ls -1t "$dir"/"$prefix"* 2>/dev/null || true; } | tail -n +"$((keep + 1))" | xargs -r rm -f --
}

backup_once() {
  local stamp daily weekly
  stamp=$(date +%Y%m%d-%H%M%S)
  daily=$BACKUP_ROOT/daily
  weekly=$BACKUP_ROOT/weekly
  mkdir -p "$daily" "$weekly"

  log "dumping $PGDATABASE"
  pg_dump --format=custom --no-owner --file="$daily/.apex-$stamp.dump.tmp"
  mv "$daily/.apex-$stamp.dump.tmp" "$daily/apex-$stamp.dump"

  if [ -d "$UPLOADS_DIR" ]; then
    tar -czf "$daily/.uploads-$stamp.tar.gz.tmp" -C "$UPLOADS_DIR" .
    mv "$daily/.uploads-$stamp.tar.gz.tmp" "$daily/uploads-$stamp.tar.gz"
  fi

  # Sunday's backup also goes to the weekly set.
  if [ "$(date +%u)" = 7 ]; then
    cp "$daily"/*-"$stamp".* "$weekly"/
  fi

  prune "$daily" apex- "$KEEP_DAILY"
  prune "$daily" uploads- "$KEEP_DAILY"
  prune "$weekly" apex- "$KEEP_WEEKLY"
  prune "$weekly" uploads- "$KEEP_WEEKLY"

  if [ -n "${BACKUP_S3_URI:-}" ]; then
    log "syncing to $BACKUP_S3_URI"
    local s3=(aws)
    [ -n "${BACKUP_S3_ENDPOINT:-}" ] && s3+=(--endpoint-url "$BACKUP_S3_ENDPOINT")
    [ -n "${BACKUP_S3_REGION:-}" ] && s3+=(--region "$BACKUP_S3_REGION")
    # Empty AWS_* variables confuse the CLI, so only set them when given.
    [ -n "${BACKUP_S3_ACCESS_KEY:-}" ] && export AWS_ACCESS_KEY_ID=$BACKUP_S3_ACCESS_KEY
    [ -n "${BACKUP_S3_SECRET_KEY:-}" ] && export AWS_SECRET_ACCESS_KEY=$BACKUP_S3_SECRET_KEY
    "${s3[@]}" s3 sync "$BACKUP_ROOT" "$BACKUP_S3_URI" --delete --only-show-errors
  fi

  touch "$BACKUP_ROOT/last-success"
  log "done: $(du -h "$daily/apex-$stamp.dump" | cut -f1) database dump"
}

case "${1:-daemon}" in
  once)
    backup_once
    ;;
  daemon)
    touch /tmp/started
    while true; do
      now=$(date +%s)
      next=$(date -d "today $HOUR:00" +%s)
      [ "$next" -le "$now" ] && next=$(date -d "tomorrow $HOUR:00" +%s)
      log "next backup at $(date -d "@$next" '+%F %T %Z')"
      sleep "$((next - now))"
      # A failed run must not kill the loop; the healthcheck turns unhealthy
      # once last-success is older than a day.
      backup_once || log "FAILED"
    done
    ;;
  *)
    echo "usage: backup.sh [daemon|once]" >&2
    exit 2
    ;;
esac

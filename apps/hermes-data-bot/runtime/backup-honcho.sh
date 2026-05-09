#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${HONCHO_BACKUP_DIR:-$HOME/.hermes/backups/honcho}"
RETENTION_DAYS="${HONCHO_BACKUP_RETENTION_DAYS:-14}"
CONTAINER="${HONCHO_POSTGRES_CONTAINER:-honcho_database_1}"
DATABASE="${HONCHO_POSTGRES_DB:-postgres}"
USER="${HONCHO_POSTGRES_USER:-postgres}"

PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PATH

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "dependency:docker:not-found"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp_file="$BACKUP_DIR/.honcho-$stamp.sql.gz.tmp"
out_file="$BACKUP_DIR/honcho-$stamp.sql.gz"

if ! docker exec "$CONTAINER" pg_dump -U "$USER" "$DATABASE" | gzip > "$tmp_file"; then
  rm -f "$tmp_file"
  fail "honcho-backup:pg-dump-failed"
fi

mv "$tmp_file" "$out_file"
chmod 600 "$out_file"
find "$BACKUP_DIR" -type f -name 'honcho-*.sql.gz' -mtime +"$RETENTION_DAYS" -delete

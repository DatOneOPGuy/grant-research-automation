#!/usr/bin/env bash
# Daily backup of the accounts database: teams, users, folders, folder items.
#
# This is the only data in the product that cannot be regenerated.
# explorer_v5.db is a compiled artifact -- lose it and you rebuild it from the
# pipeline. A saved folder is something a person decided, and there is no
# second copy of it anywhere.
#
# Installed as a systemd timer; see DEPLOY.md. Run by hand at any time:
#     /opt/fcf/scripts/backup-accounts.sh

set -euo pipefail

DEST=/var/backups/fcf
KEEP_DAYS=30
STAMP=$(date -u +%Y-%m-%dT%H%M%SZ)
OUT="${DEST}/accounts-${STAMP}.sql.gz"

mkdir -p "$DEST"
# 700: these dumps carry real user email addresses.
chmod 700 "$DEST"

# --format=plain so a restore needs nothing but psql, and so the file can be
# read with zcat when someone is trying to answer "what was in that folder?"
sudo -u postgres pg_dump --format=plain --no-owner --no-privileges fcf \
  | gzip > "${OUT}.partial"

# Only becomes a backup once it is complete. A truncated dump that looks like
# a backup is worse than an obvious absence.
if ! gzip -t "${OUT}.partial" 2>/dev/null; then
  echo "backup FAILED: ${OUT}.partial is not a valid archive" >&2
  rm -f "${OUT}.partial"
  exit 1
fi

# A dump with no COPY block restored cleanly and silently produced an empty
# database, so check the contents rather than just the exit status.
if ! zcat "${OUT}.partial" | grep -q "COPY public.users"; then
  echo "backup FAILED: no users table in the dump" >&2
  rm -f "${OUT}.partial"
  exit 1
fi

mv "${OUT}.partial" "$OUT"
chmod 600 "$OUT"

ROWS=$(zcat "$OUT" | grep -c "^[0-9]" || true)
echo "wrote $OUT ($(du -h "$OUT" | cut -f1), ~${ROWS} data rows)"

# Retention. -mtime +N deletes strictly older than N days, so KEEP_DAYS=30
# keeps roughly a month of dailies.
DELETED=$(find "$DEST" -name 'accounts-*.sql.gz' -mtime "+${KEEP_DAYS}" -print -delete | wc -l)
[ "$DELETED" -gt 0 ] && echo "pruned ${DELETED} backup(s) older than ${KEEP_DAYS} days"

echo "retained: $(find "$DEST" -name 'accounts-*.sql.gz' | wc -l) file(s)"

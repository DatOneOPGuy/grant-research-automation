#!/usr/bin/env bash
# Start the whole local stack: Postgres, the API, and the Vite dev server.
#
#   scripts/dev.sh          start everything
#   scripts/dev.sh stop     stop everything
#
# Exists because starting the API without DATABASE_URL is silent: it comes up
# healthy, serves all the read routes, and only saved folders fail -- with a
# 503 the page renders once at mount and then never retries. The result looks
# like "saving is broken" when it is really "the API was started without a
# database". This makes the working configuration the easy one.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PGBIN="/opt/homebrew/opt/postgresql@14/bin"
PGDATA="${ROOT}/.devdata/pgdata"
PGPORT=55432
DB_URL="postgresql+psycopg://postgres@127.0.0.1:${PGPORT}/fcf_local"
API_PORT=8000
WEB_PORT=5173

stop() {
  pkill -f "uvicorn main_v5" 2>/dev/null || true
  pkill -f "vite --port ${WEB_PORT}" 2>/dev/null || true
  [ -d "$PGDATA" ] && "${PGBIN}/pg_ctl" -D "$PGDATA" stop >/dev/null 2>&1 || true
  echo "stopped"
}

if [ "${1:-start}" = "stop" ]; then stop; exit 0; fi

export PATH="${PGBIN}:${PATH}"

# --- Postgres ---------------------------------------------------------------
# Kept under .devdata so it survives between sessions; the scratch database in
# /tmp did not, and every restart silently lost the folders being tested.
if [ ! -d "$PGDATA" ]; then
  echo "initialising local Postgres..."
  mkdir -p "$(dirname "$PGDATA")"
  initdb -D "$PGDATA" -U postgres >/dev/null
fi
if ! pg_isready -h 127.0.0.1 -p "$PGPORT" >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" -o "-p ${PGPORT} -h 127.0.0.1 -k /tmp" \
         -l "${PGDATA}/../pg.log" start >/dev/null
  sleep 2
fi
psql -h 127.0.0.1 -p "$PGPORT" -U postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='fcf_local'" | grep -q 1 \
  || createdb -h 127.0.0.1 -p "$PGPORT" -U postgres fcf_local
echo "postgres      ready on :${PGPORT}"

# --- schema -----------------------------------------------------------------
cd "${ROOT}/foundation-explorer/backend"
DATABASE_URL="$DB_URL" .venv/bin/alembic upgrade head >/dev/null 2>&1
echo "migrations    applied"

# --- API --------------------------------------------------------------------
pkill -f "uvicorn main_v5" 2>/dev/null || true
sleep 1
DATABASE_URL="$DB_URL" DEV_USER_EMAIL="dev@example.com" \
  nohup .venv/bin/uvicorn main_v5:app --host 127.0.0.1 --port "$API_PORT" \
  > /tmp/fcf-api.log 2>&1 &
for _ in $(seq 1 20); do
  sleep 1
  if curl -sf "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; then break; fi
done
ACCOUNTS=$(curl -s "http://127.0.0.1:${API_PORT}/api/health" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['accounts']['status'])")
echo "api           :${API_PORT}  accounts=${ACCOUNTS}"
[ "$ACCOUNTS" = "ok" ] || { echo "ERROR: accounts not ok — saved folders will 503"; exit 1; }

# --- frontend ---------------------------------------------------------------
cd "${ROOT}/foundation-explorer/frontend"
pkill -f "vite --port ${WEB_PORT}" 2>/dev/null || true
sleep 1
nohup npx vite --port "$WEB_PORT" --strictPort > /tmp/fcf-web.log 2>&1 &
for _ in $(seq 1 20); do
  sleep 1
  if curl -sf "http://localhost:${WEB_PORT}/" >/dev/null 2>&1; then break; fi
done
echo "frontend      http://localhost:${WEB_PORT}"
echo
echo "logs: /tmp/fcf-api.log  /tmp/fcf-web.log"

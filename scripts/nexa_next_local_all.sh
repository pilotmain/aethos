#!/usr/bin/env bash
# Nexa Next — native “run it all” helper (distinct name from ./run_everything.sh).
#
# Starts the FastAPI app + Next.js dev server on non-default ports so you can run this repo
# beside another Nexa stack (typical clash: API :8010 + web :3000).
#
# Defaults (override anytime):
#   NEXA_NEXT_API_PORT=8120   → API + OpenAPI docs
#   NEXA_NEXT_WEB_PORT=3120   → Mission Control / web UI
#
# Usage:
#   ./scripts/nexa_next_local_all.sh start    # API + web + Telegram bot (when TELEGRAM_BOT_TOKEN is set in .env)
#   ./scripts/nexa_next_local_all.sh stop
#   ./scripts/nexa_next_local_all.sh status
#
# Database (important):
#   By default this script sets NEXA_NEXT_LOCAL_SIDECAR=1 so the app uses repo-root SQLite
#   (overwhelm_reset.db) even if .env says postgresql://127.0.0.1:5434 — avoiding "connection refused"
#   when Docker Postgres is not running.
#   To use Postgres from .env instead, start the DB first:
#     NEXA_NEXT_LOCAL_START_POSTGRES=1 ./scripts/nexa_next_local_all.sh start
#   (requires Docker; starts `docker compose` service `db` using POSTGRES_HOST_PORT from .env.)
#
# Bot: starts automatically if .env contains a non-empty TELEGRAM_BOT_TOKEN. Opt out with:
#   NEXA_NEXT_START_BOT=0   (or false / no)
#
# Running only the bot (manual): use ./scripts/run_telegram_bot_local.sh — do not use a random global
# Python/venv without NEXA_NEXT_LOCAL_SIDECAR=1 or you will hit Postgres connection errors.
#
# Important: run only ``start`` if you want the stack to stay up. Running ``stop`` tears down
# API + web — so do not chain ``start`` then ``stop`` unless you mean to shut down immediately.
#
# Prerequisites: Python venv at repo .venv (pip install -r requirements.txt); npm install in web/

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${NEXA_NEXT_API_PORT:-8120}"
WEB_PORT="${NEXA_NEXT_WEB_PORT:-3120}"

RUNTIME="${ROOT}/.runtime"
API_LOG="${RUNTIME}/nexa_next_local_api.log"
WEB_LOG="${RUNTIME}/nexa_next_local_web.log"
BOT_LOG="${RUNTIME}/nexa_next_local_bot.log"
API_PIDF="${RUNTIME}/nexa_next_local_api.pid"
WEB_PIDF="${RUNTIME}/nexa_next_local_web.pid"
BOT_PIDF="${RUNTIME}/nexa_next_local_bot.pid"

PYTHON="${ROOT}/.venv/bin/python"
UVICORN="${ROOT}/.venv/bin/uvicorn"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
  UVICORN="uvicorn"
fi

api_health_url() {
  echo "http://127.0.0.1:${API_PORT}/api/v1/health"
}

stop_pidfile() {
  local pf="$1"
  if [ -f "$pf" ]; then
    local pid
    pid="$(cat "$pf" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pf"
  fi
}

# Uvicorn --reload replaces the supervisor PID; pidfiles can go stale. Always clear listeners.
kill_listeners_on_port() {
  local port="$1"
  [ -n "${port:-}" ] || return 0
  if ! command -v lsof &>/dev/null; then
    return 0
  fi
  local pids
  pids="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [ -z "${pids:-}" ]; then
    return 0
  fi
  # shellcheck disable=SC2086
  kill ${pids} 2>/dev/null || true
  sleep 1
  # shellcheck disable=SC2086
  kill -9 ${pids} 2>/dev/null || true
}

cmd_stop() {
  stop_pidfile "$API_PIDF"
  stop_pidfile "$WEB_PIDF"
  stop_pidfile "$BOT_PIDF"
  kill_listeners_on_port "$API_PORT"
  kill_listeners_on_port "$WEB_PORT"
  echo "Stopped (nexa_next_local pidfiles cleared: API, web, bot; listeners on ports ${API_PORT}/${WEB_PORT} released)."
}

_one_proc_status() {
  local name="$1" pf="$2"
  if [ -f "$pf" ]; then
    pid="$(cat "$pf" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      echo "${name}: running pid=${pid}"
    else
      echo "${name}: stale pid file"
    fi
  else
    echo "${name}: not started"
  fi
}

_postgres_host_port_from_env_file() {
  local f="$ROOT/.env"
  [ -f "$f" ] || { echo "5433"; return 0; }
  local line
  line="$(grep -E '^[[:space:]]*POSTGRES_HOST_PORT=' "$f" 2>/dev/null | tail -1 || true)"
  [ -n "${line:-}" ] || { echo "5433"; return 0; }
  line="${line#*=}"
  line="${line// /}"
  line="${line//\"/}"
  line="${line//\'/}"
  echo "${line:-5433}"
}

_wait_for_tcp() {
  local host="$1" port="$2" max="${3:-50}"
  local i=0
  echo -n "Waiting for ${host}:${port} … " >&2
  while [ "$i" -lt "$max" ]; do
    if command -v nc &>/dev/null; then
      nc -z "$host" "$port" 2>/dev/null && { echo "OK" >&2; return 0; }
    elif "$PYTHON" - <<PY 2>/dev/null
import socket, sys
s = socket.socket()
s.settimeout(0.4)
try:
    s.connect(("${host}", int("${port}")))
    s.close()
    sys.exit(0)
except OSError:
    sys.exit(1)
PY
    then
      echo "OK" >&2
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  echo "timed out" >&2
  return 1
}

cmd_status() {
  echo "Configured ports: API=${API_PORT} WEB=${WEB_PORT}"
  echo "Health: $(api_health_url)"
  local api_up=""
  if command -v curl &>/dev/null; then
    if curl -fsS --connect-timeout 2 --max-time 4 "$(api_health_url)" >/dev/null 2>&1; then
      api_up=1
      echo "API: responding (HTTP health OK on port ${API_PORT})"
    else
      echo "API: not responding yet or stopped"
    fi
  else
    echo "API: install curl for automatic health check"
  fi
  _one_proc_status "PID file (API)" "$API_PIDF"
  _one_proc_status "PID file (Web)" "$WEB_PIDF"
  _one_proc_status "PID file (Bot)" "$BOT_PIDF"
  if [ -n "${api_up:-}" ] && [ -f "$API_PIDF" ]; then
    pid="$(cat "$API_PIDF" 2>/dev/null || true)"
    if [ -z "${pid:-}" ] || ! kill -0 "$pid" 2>/dev/null; then
      echo "Note: with uvicorn --reload, the saved API pid may be stale; trust 'responding' above."
    fi
  fi
}

cmd_start() {
  mkdir -p "$RUNTIME"

  export API_BASE_URL="http://127.0.0.1:${API_PORT}"
  export NEXA_WEB_ORIGINS="http://localhost:${WEB_PORT},http://127.0.0.1:${WEB_PORT}"

  _start_pg=0
  case "${NEXA_NEXT_LOCAL_START_POSTGRES:-}" in
    1|true|TRUE|yes|YES) _start_pg=1 ;;
  esac
  if [ "$_start_pg" -eq 1 ]; then
    if command -v docker &>/dev/null && [ -f "${ROOT}/docker-compose.yml" ]; then
      echo "Starting Postgres via Docker (service db); using DATABASE_URL from .env (SQLite sidcar off)."
      (cd "$ROOT" && docker compose up -d db)
      _pg_port="$(_postgres_host_port_from_env_file)"
      export POSTGRES_HOST_PORT="${_pg_port}"
      if ! _wait_for_tcp 127.0.0.1 "$_pg_port" 55; then
        echo "Postgres did not become reachable; falling back to SQLite (NEXA_NEXT_LOCAL_SIDECAR=1)." >&2
        export NEXA_NEXT_LOCAL_SIDECAR=1
      else
        export NEXA_NEXT_LOCAL_SIDECAR=0
      fi
    else
      echo "NEXA_NEXT_LOCAL_START_POSTGRES=1 but docker or docker-compose.yml missing — using SQLite sidcar." >&2
      export NEXA_NEXT_LOCAL_SIDECAR=1
    fi
  else
    export NEXA_NEXT_LOCAL_SIDECAR=1
    echo "Local DB: SQLite at ${ROOT}/overwhelm_reset.db (NEXA_NEXT_LOCAL_SIDECAR=1; Postgres in .env ignored)."
  fi

  if [ -f "$API_PIDF" ]; then
    old="$(cat "$API_PIDF" 2>/dev/null || true)"
    if [ -n "${old:-}" ] && kill -0 "$old" 2>/dev/null; then
      echo "API already running (pid ${old}). Stop first or run: $0 stop" >&2
      exit 1
    fi
    rm -f "$API_PIDF"
  fi

  echo "Starting API (uvicorn) on 0.0.0.0:${API_PORT} …"
  # Pass DB mode explicitly so nohup children match this shell even if .env differs.
  if [ "${NEXA_NEXT_LOCAL_SIDECAR:-1}" = "1" ] || [ "${NEXA_NEXT_LOCAL_SIDECAR:-}" = "true" ]; then
    nohup env NEXA_NEXT_LOCAL_SIDECAR=1 API_BASE_URL="${API_BASE_URL}" NEXA_WEB_ORIGINS="${NEXA_WEB_ORIGINS}" \
      "$UVICORN" app.main:app --reload --host 0.0.0.0 --port "${API_PORT}" >>"$API_LOG" 2>&1 &
  else
    nohup env NEXA_NEXT_LOCAL_SIDECAR=0 API_BASE_URL="${API_BASE_URL}" NEXA_WEB_ORIGINS="${NEXA_WEB_ORIGINS}" \
      "$UVICORN" app.main:app --reload --host 0.0.0.0 --port "${API_PORT}" >>"$API_LOG" 2>&1 &
  fi
  echo $! >"$API_PIDF"

  echo "Starting Next.js on port ${WEB_PORT} (API base → ${API_BASE_URL}) …"
  (
    cd "${ROOT}/web"
    export NEXT_PUBLIC_NEXA_API_BASE="http://127.0.0.1:${API_PORT}"
    if [ -x "${ROOT}/web/node_modules/.bin/next" ]; then
      nohup "${ROOT}/web/node_modules/.bin/next" dev -p "${WEB_PORT}" >>"$WEB_LOG" 2>&1 &
    else
      nohup npx --yes next dev -p "${WEB_PORT}" >>"$WEB_LOG" 2>&1 &
    fi
    echo $! >"$WEB_PIDF"
  )

  # Telegram bot: run by default when token is set (same as: .venv/bin/python -m app.bot.telegram_bot).
  # Disable with NEXA_NEXT_START_BOT=0 (or false / no) if you only want API + web.
  _skip_bot=0
  case "${NEXA_NEXT_START_BOT:-}" in
    0|false|no|NO|False) _skip_bot=1 ;;
  esac
  _has_bot_token=0
  if [ -f "${ROOT}/.env" ] && "$PYTHON" -c "
import re
from pathlib import Path
p = Path(r'''${ROOT}''') / '.env'
t = p.read_text(encoding='utf-8', errors='replace')
for ln in t.splitlines():
    s = ln.strip()
    if not s or s.startswith('#'):
        continue
    m = re.match(r'^(?:export\s+)?TELEGRAM_BOT_TOKEN\s*=\s*(.*)$', s, re.I)
    if not m:
        continue
    v = m.group(1).strip().strip('\"').strip(\"'\")
    raise SystemExit(0 if v else 1)
raise SystemExit(1)
" 2>/dev/null; then
    _has_bot_token=1
  fi
  if [ "$_skip_bot" -eq 0 ] && [ "$_has_bot_token" -eq 1 ]; then
    echo "Starting Telegram bot (python -m app.bot.telegram_bot, same DB mode as API) …"
    if [ "${NEXA_NEXT_LOCAL_SIDECAR:-1}" = "1" ] || [ "${NEXA_NEXT_LOCAL_SIDECAR:-}" = "true" ]; then
      nohup env NEXA_NEXT_LOCAL_SIDECAR=1 API_BASE_URL="${API_BASE_URL}" "$PYTHON" -m app.bot.telegram_bot >>"$BOT_LOG" 2>&1 &
    else
      nohup env NEXA_NEXT_LOCAL_SIDECAR=0 API_BASE_URL="${API_BASE_URL}" "$PYTHON" -m app.bot.telegram_bot >>"$BOT_LOG" 2>&1 &
    fi
    echo $! >"$BOT_PIDF"
    echo "  Bot log: ${BOT_LOG}"
  elif [ "$_skip_bot" -eq 1 ]; then
    echo "Bot skipped (NEXA_NEXT_START_BOT disables bot; unset or set to 1 to enable when token is present)." >&2
  else
    echo "Bot skipped (no non-empty TELEGRAM_BOT_TOKEN in ${ROOT}/.env)." >&2
  fi

  echo ""
  echo "--- Nexa Next (sidecar ports) ---"
  echo "  API (docs):  http://127.0.0.1:${API_PORT}/docs"
  echo "  Web UI:      http://127.0.0.1:${WEB_PORT}"
  echo "  Health:      $(api_health_url)"
  echo "Logs: ${API_LOG}"
  echo "      ${WEB_LOG}"
  if [ -f "$BOT_PIDF" ]; then
    echo "      ${BOT_LOG}"
  fi
  echo ""
  echo "Leave these processes running. Open another terminal for other commands."
  echo "Running \"$0 stop\" shuts API + web down — only use it when you are finished."
  echo ""
  echo "In the web app Login / Connection, set API base to: http://127.0.0.1:${API_PORT}"
  echo "Check: $0 status   |   Stop later: $0 stop"

  if command -v curl &>/dev/null; then
    local i=0
    echo -n "Waiting for API health … " >&2
    while [ "$i" -lt 45 ]; do
      if curl -fsS --connect-timeout 1 --max-time 3 "$(api_health_url)" >/dev/null 2>&1; then
        echo "OK" >&2
        return 0
      fi
      sleep 1
      i=$((i + 1))
    done
    echo "timed out (see ${API_LOG})" >&2
  fi
}

main() {
  case "${1:-start}" in
    start) cmd_start ;;
    stop) cmd_stop ;;
    status) cmd_status ;;
    -h|--help)
      sed -n '1,20p' "$0"
      ;;
    *)
      echo "Usage: $0 {start|stop|status}" >&2
      exit 2
      ;;
  esac
}

main "$@"

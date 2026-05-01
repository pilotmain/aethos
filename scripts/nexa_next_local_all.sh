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
#   ./scripts/nexa_next_local_all.sh start    # API + web in background (optional Telegram bot)
#   ./scripts/nexa_next_local_all.sh stop
#   ./scripts/nexa_next_local_all.sh status
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
  echo "Stopped (nexa_next_local pidfiles cleared; listeners on ports ${API_PORT}/${WEB_PORT} released)."
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
  # Forces SQLite in app when .env points at Postgres that is not running (see app/core/config.py).
  export NEXA_NEXT_LOCAL_SIDECAR=1

  if [ -f "$API_PIDF" ]; then
    old="$(cat "$API_PIDF" 2>/dev/null || true)"
    if [ -n "${old:-}" ] && kill -0 "$old" 2>/dev/null; then
      echo "API already running (pid ${old}). Stop first or run: $0 stop" >&2
      exit 1
    fi
    rm -f "$API_PIDF"
  fi

  echo "Starting API (uvicorn) on 0.0.0.0:${API_PORT} …"
  nohup "$UVICORN" app.main:app --reload --host 0.0.0.0 --port "${API_PORT}" >>"$API_LOG" 2>&1 &
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

  if [ "${NEXA_NEXT_START_BOT:-}" = "1" ] || [ "${NEXA_NEXT_START_BOT:-}" = "true" ]; then
    if [ -f "${ROOT}/.env" ] && grep -qE '^[[:space:]]*TELEGRAM_BOT_TOKEN[[:space:]]*=' "${ROOT}/.env"; then
      echo "Starting Telegram bot …"
      nohup "$PYTHON" -m app.bot.telegram_bot >>"$BOT_LOG" 2>&1 &
      echo $! >"$BOT_PIDF"
    else
      echo "Skipping bot (set TELEGRAM_BOT_TOKEN in .env and NEXA_NEXT_START_BOT=1 to enable)." >&2
    fi
  else
    echo "Bot skipped (export NEXA_NEXT_START_BOT=1 with TELEGRAM_BOT_TOKEN in .env to run it)." >&2
  fi

  echo ""
  echo "--- Nexa Next (sidecar ports) ---"
  echo "  API (docs):  http://127.0.0.1:${API_PORT}/docs"
  echo "  Web UI:      http://127.0.0.1:${WEB_PORT}"
  echo "  Health:      $(api_health_url)"
  echo "Logs: ${API_LOG}"
  echo "      ${WEB_LOG}"
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

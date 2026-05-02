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
#   ./scripts/nexa_next_local_all.sh start    # One local command: Docker + web (+ native API when not using full compose)
#   ./scripts/nexa_next_local_all.sh stop
#   ./scripts/nexa_next_local_all.sh status
#
# Default flow (NEXA_NEXT_LOCAL_FULL_STACK=1 or unset):
#   1. docker compose up --build -d   → Postgres + API (:8010) + Telegram bot (containers nexa-db / nexa-api / nexa-bot)
#   2. Host Next.js dev server → Mission Control (points at Docker API :8010)
#   Host uvicorn + host Telegram bot are skipped (containers already run them).
#
# Native dev API with hot reload (no compose API/bot containers):
#   NEXA_NEXT_LOCAL_FULL_STACK=0 ./scripts/nexa_next_local_all.sh start
#   Then: ./scripts/docker_postgres_up.sh runs when .env uses Postgres (same as before), host API on NEXA_NEXT_API_PORT
#   (default 8120), host bot if TELEGRAM_BOT_TOKEN is set.
#
# Database (native mode):
#   Override: NEXA_NEXT_LOCAL_START_POSTGRES=0 — never start Docker db; force SQLite sidcar.
#   Override: NEXA_NEXT_LOCAL_START_POSTGRES=1 — always run docker_postgres_up.sh first.
#   If Docker is missing or db fails, falls back to SQLite at ${ROOT}/overwhelm_reset.db.
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
# Published host port for docker-compose ``api`` service (see docker-compose.yml).
COMPOSE_API_PORT="${NEXA_NEXT_COMPOSE_API_PORT:-8010}"

RUNTIME="${ROOT}/.runtime"
STACK_MODE_FILE="${RUNTIME}/nexa_next_local_stack_mode"
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

compose_api_health_url() {
  echo "http://127.0.0.1:${COMPOSE_API_PORT}/api/v1/health"
}

_env_database_url_looks_like_postgres() {
  [ -f "${ROOT}/.env" ] || return 1
  grep -qiE '^[[:space:]]*DATABASE_URL=.*postgres' "${ROOT}/.env" 2>/dev/null
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
  if [ -f "$STACK_MODE_FILE" ] && grep -q '^compose$' "$STACK_MODE_FILE" 2>/dev/null; then
    if command -v docker &>/dev/null && [ -f "${ROOT}/docker-compose.yml" ]; then
      echo "Stopping Docker Compose stack (db, api, bot) …"
      (cd "$ROOT" && docker compose stop 2>/dev/null || true)
    fi
    rm -f "$STACK_MODE_FILE"
  fi
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
  echo "Configured ports: native API=${API_PORT} compose API=${COMPOSE_API_PORT} WEB=${WEB_PORT}"
  if [ -f "$STACK_MODE_FILE" ] && grep -q '^compose$' "$STACK_MODE_FILE" 2>/dev/null; then
    echo "Last start used Docker Compose for API+bot+db — health: $(compose_api_health_url)"
    if command -v docker &>/dev/null; then
      (cd "$ROOT" && docker compose ps 2>/dev/null) || true
    fi
  fi
  echo "Native health: $(api_health_url)"
  local api_up=""
  if command -v curl &>/dev/null; then
    if curl -fsS --connect-timeout 2 --max-time 4 "$(api_health_url)" >/dev/null 2>&1; then
      api_up=1
      echo "Native API: responding on port ${API_PORT}"
    else
      echo "Native API: not responding on port ${API_PORT}"
    fi
    if curl -fsS --connect-timeout 2 --max-time 4 "$(compose_api_health_url)" >/dev/null 2>&1; then
      echo "Compose API: responding on port ${COMPOSE_API_PORT}"
    else
      echo "Compose API: not responding on port ${COMPOSE_API_PORT}"
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

  _use_compose_stack=0
  _try_compose=0
  case "${NEXA_NEXT_LOCAL_FULL_STACK:-1}" in
    1|true|TRUE|yes|YES) _try_compose=1 ;;
    0|false|no|NO|False)
      _try_compose=0
      rm -f "$STACK_MODE_FILE"
      ;;
    *) _try_compose=1 ;;
  esac

  if [ "$_try_compose" -eq 1 ] && command -v docker &>/dev/null && [ -f "${ROOT}/docker-compose.yml" ]; then
    echo "=== docker compose up --build -d (db + api + bot containers) ==="
    if (cd "$ROOT" && docker compose up --build -d); then
      echo compose >"$STACK_MODE_FILE"
      _use_compose_stack=1
    else
      echo "docker compose up failed — falling back to host API/bot if possible." >&2
      rm -f "$STACK_MODE_FILE"
    fi
  elif [ "$_try_compose" -eq 1 ]; then
    echo "Docker or docker-compose.yml missing — using host-only stack." >&2
    rm -f "$STACK_MODE_FILE"
  fi

  export NEXA_WEB_ORIGINS="http://localhost:${WEB_PORT},http://127.0.0.1:${WEB_PORT}"

  if [ "$_use_compose_stack" -eq 1 ]; then
    export API_BASE_URL="http://127.0.0.1:${COMPOSE_API_PORT}"
    echo ""
    echo "Docker Compose is serving API on :${COMPOSE_API_PORT} and Telegram bot in container (nexa-bot)."
    echo "Host uvicorn + host bot are skipped — use: docker compose logs -f bot"
    echo ""
  else
    export API_BASE_URL="http://127.0.0.1:${API_PORT}"

    # Native mode: Postgres via ./scripts/docker_postgres_up.sh when .env is Postgres (same as manual script).
    _start_pg=0
    case "${NEXA_NEXT_LOCAL_START_POSTGRES:-}" in
      1|true|TRUE|yes|YES) _start_pg=1 ;;
      0|false|no|NO|False) _start_pg=0 ;;
      *)
        if _env_database_url_looks_like_postgres && command -v docker &>/dev/null && [ -f "${ROOT}/docker-compose.yml" ]; then
          _start_pg=1
        fi
        ;;
    esac
    if [ "$_start_pg" -eq 1 ]; then
      if [ -x "${ROOT}/scripts/docker_postgres_up.sh" ]; then
        echo "=== ./scripts/docker_postgres_up.sh (Docker db only for host processes) ==="
        if bash "${ROOT}/scripts/docker_postgres_up.sh"; then
          export NEXA_NEXT_LOCAL_SIDECAR=0
        else
          echo "docker_postgres_up failed — using SQLite sidcar for host API." >&2
          export NEXA_NEXT_LOCAL_SIDECAR=1
        fi
      elif command -v docker &>/dev/null && [ -f "${ROOT}/docker-compose.yml" ]; then
        echo "Starting Postgres via Docker (service db) …"
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
        export NEXA_NEXT_LOCAL_SIDECAR=1
      fi
    else
      export NEXA_NEXT_LOCAL_SIDECAR=1
      if _env_database_url_looks_like_postgres; then
        echo "Local DB: SQLite at ${ROOT}/overwhelm_reset.db (NEXA_NEXT_LOCAL_SIDECAR=1)."
        echo "  Hint: install Docker or run ./scripts/docker_postgres_up.sh before start." >&2
      else
        echo "Local DB: SQLite at ${ROOT}/overwhelm_reset.db (NEXA_NEXT_LOCAL_SIDECAR=1)."
      fi
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
    if [ "${NEXA_NEXT_LOCAL_SIDECAR:-1}" = "1" ] || [ "${NEXA_NEXT_LOCAL_SIDECAR:-}" = "true" ]; then
      nohup env NEXA_NEXT_LOCAL_SIDECAR=1 API_BASE_URL="${API_BASE_URL}" NEXA_WEB_ORIGINS="${NEXA_WEB_ORIGINS}" \
        "$UVICORN" app.main:app --reload --host 0.0.0.0 --port "${API_PORT}" >>"$API_LOG" 2>&1 &
    else
      nohup env NEXA_NEXT_LOCAL_SIDECAR=0 API_BASE_URL="${API_BASE_URL}" NEXA_WEB_ORIGINS="${NEXA_WEB_ORIGINS}" \
        "$UVICORN" app.main:app --reload --host 0.0.0.0 --port "${API_PORT}" >>"$API_LOG" 2>&1 &
    fi
    echo $! >"$API_PIDF"

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
      echo "Starting Telegram bot (host python -m app.bot.telegram_bot) …"
      if [ "${NEXA_NEXT_LOCAL_SIDECAR:-1}" = "1" ] || [ "${NEXA_NEXT_LOCAL_SIDECAR:-}" = "true" ]; then
        nohup env NEXA_NEXT_LOCAL_SIDECAR=1 API_BASE_URL="${API_BASE_URL}" "$PYTHON" -m app.bot.telegram_bot >>"$BOT_LOG" 2>&1 &
      else
        nohup env NEXA_NEXT_LOCAL_SIDECAR=0 API_BASE_URL="${API_BASE_URL}" "$PYTHON" -m app.bot.telegram_bot >>"$BOT_LOG" 2>&1 &
      fi
      echo $! >"$BOT_PIDF"
      echo "  Bot log: ${BOT_LOG}"
    elif [ "$_skip_bot" -eq 1 ]; then
      echo "Bot skipped (NEXA_NEXT_START_BOT disables bot)." >&2
    else
      echo "Bot skipped (no TELEGRAM_BOT_TOKEN in ${ROOT}/.env)." >&2
    fi
  fi

  _next_api_port="${API_PORT}"
  if [ "$_use_compose_stack" -eq 1 ]; then
    _next_api_port="${COMPOSE_API_PORT}"
  fi

  echo "Starting Next.js on port ${WEB_PORT} (API base → http://127.0.0.1:${_next_api_port}) …"
  (
    cd "${ROOT}/web"
    export NEXT_PUBLIC_NEXA_API_BASE="http://127.0.0.1:${_next_api_port}"
    if [ -x "${ROOT}/web/node_modules/.bin/next" ]; then
      nohup "${ROOT}/web/node_modules/.bin/next" dev -p "${WEB_PORT}" >>"$WEB_LOG" 2>&1 &
    else
      nohup npx --yes next dev -p "${WEB_PORT}" >>"$WEB_LOG" 2>&1 &
    fi
    echo $! >"$WEB_PIDF"
  )

  echo ""
  echo "--- Nexa Next local ---"
  if [ "$_use_compose_stack" -eq 1 ]; then
    echo "  Compose API: http://127.0.0.1:${COMPOSE_API_PORT}/docs   Health: $(compose_api_health_url)"
    echo "  Telegram bot: container nexa-bot (docker compose logs -f bot)"
    echo "  Web UI:       http://127.0.0.1:${WEB_PORT}  → API :${COMPOSE_API_PORT}"
  else
    echo "  API (docs):   http://127.0.0.1:${API_PORT}/docs"
    echo "  Web UI:       http://127.0.0.1:${WEB_PORT}"
    echo "  Health:       $(api_health_url)"
  fi
  echo "Logs: ${API_LOG}"
  echo "      ${WEB_LOG}"
  if [ -f "$BOT_PIDF" ]; then
    echo "      ${BOT_LOG}"
  fi
  echo ""
  echo "Leave these processes running. \"$0 stop\" stops host processes and (if used) docker compose stop."
  echo "Login / Connection API base: http://127.0.0.1:${_next_api_port}"
  echo "Check: $0 status   |   Stop: $0 stop"

  if command -v curl &>/dev/null; then
    local i=0
    local _health_url
    local _max_wait
    if [ "$_use_compose_stack" -eq 1 ]; then
      _health_url="$(compose_api_health_url)"
      _max_wait=120
      echo -n "Waiting for Compose API health … " >&2
    else
      _health_url="$(api_health_url)"
      _max_wait=45
      echo -n "Waiting for native API health … " >&2
    fi
    while [ "$i" -lt "$_max_wait" ]; do
      if curl -fsS --connect-timeout 1 --max-time 3 "$_health_url" >/dev/null 2>&1; then
        echo "OK" >&2
        return 0
      fi
      sleep 1
      i=$((i + 1))
    done
    echo "timed out (first build can be slow; try: docker compose logs api)" >&2
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

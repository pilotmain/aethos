#!/usr/bin/env bash
# One entrypoint for the full Nexa stack.
#
# Docker (default) — Postgres or SQLite compose + API (uvicorn; in-process APScheduler: follow-ups +
# operator → may spawn local_tool_worker / dev executor as subprocesses) + Telegram bot + optional
# Next.js web (:3000) + optional host dev executor (DEV_EXECUTOR_ON_HOST=1 in .env; needs .venv on host).
#
#   ./run_everything.sh start          # background: db + api + bot; web on :3000; host dev if enabled
#   ./run_everything.sh                # dev: docker compose watch (or up) + web; Ctrl+C may leave containers up
#   USE_SQLITE=1 ./run_everything.sh start
#   ./run_everything.sh sqlite start   # same as USE_SQLITE=1
#   ./run_everything.sh stop | status | logs | build
#
# Native (no Docker) — local .venv + scripts/start_operator_stack.sh (API + bot on host) + same web + host dev:
#
#   ./run_everything.sh native start   # or: ./run_everything.sh native
#   ./run_everything.sh native stop
#
# start / daemon / listen / background / up-bg / always = same as --detach for Docker.
# Compose v2.22+ for `docker compose watch` (dev use).
#   For code-only updates on a started stack: `docker compose build` then `up -d` (or re-run: ./run_everything.sh start)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Used after API is supposed to be up (Docker or native).
API_HEALTH_URL="${API_HEALTH_URL:-http://127.0.0.1:8010/api/v1/health}"
WAIT_API_HEALTH_SECONDS="${WAIT_API_HEALTH_SECONDS:-120}"

wait_api_healthy() {
  local url="${1:-$API_HEALTH_URL}"
  local max="${2:-$WAIT_API_HEALTH_SECONDS}"
  local i=0 step=2
  if ! command -v curl &>/dev/null; then
    echo "warning: curl not found — skipping API health wait (install curl for a startup gate)" >&2
    return 0
  fi
  echo "Waiting for API health (${url})…" >&2
  while [ "$i" -lt "$max" ]; do
    if curl -fsS --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1; then
      echo "API is healthy." >&2
      return 0
    fi
    sleep "$step"
    i=$((i + step))
  done
  echo "warning: API did not respond healthy within ${max}s — try: ./run_everything.sh logs" >&2
  return 1
}

warn_venv_if_host_dev_enabled() {
  if ! _wants_host_dev_from_env; then
    return 0
  fi
  if [ -x "${ROOT}/.venv/bin/python3" ]; then
    return 0
  fi
  echo "warning: DEV_EXECUTOR_ON_HOST=1 but ${ROOT}/.venv is missing or has no python3." >&2
  echo "  Host dev executor will be skipped until you run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
}

NATIVE_STACK=0
if [ "${1:-}" = "native" ] || [ "${1:-}" = "local" ]; then
  NATIVE_STACK=1
  shift
fi

COMPOSE_ARGS=(-f "${ROOT}/docker-compose.yml")
if [ "$NATIVE_STACK" != "1" ] && { [ "${USE_SQLITE:-0}" = "1" ] || [ "${1:-}" = "sqlite" ]; }; then
  COMPOSE_ARGS=(-f "${ROOT}/docker-compose.sqlite.yml")
  if [ "${1:-}" = "sqlite" ]; then
    set -- "${@:2}" # drop first arg
  fi
fi

# Modes: start|daemon|listen|background|up-bg|always  →  same as --detach (always-on, no watch)
START_ALWAYS=0
if [ "${1:-}" = "start" ] || [ "${1:-}" = "daemon" ] || [ "${1:-}" = "background" ] || [ "${1:-}" = "listen" ] || [ "${1:-}" = "up-bg" ] || [ "${1:-}" = "always" ]; then
  START_ALWAYS=1
  shift
fi

# Used for startup URL banner (Postgres only when not SQLite compose file)
IS_SQLITE_STACK=0
[[ "${COMPOSE_ARGS[*]}" == *"sqlite.yml"* ]] && IS_SQLITE_STACK=1

dc() { docker compose "${COMPOSE_ARGS[@]}" "$@"; }

# Default must match ${POSTGRES_HOST_PORT:-5433} in docker-compose.yml
published_pg_port() {
  local d=5433 m v
  if [ -f .env ] && m=$(grep -E '^[[:space:]]*POSTGRES_HOST_PORT[[:space:]]*=' .env 2>/dev/null | tail -1); then
    v="${m#*=}"
    v="${v%$'\r'}"
    v="${v#"${v%%[![:space:]]*}"}"; v="${v%"${v##*[![:space:]]}"}"
    v="${v%%#*}"
    v="${v//\"/}"; v="${v//\'}"
    v="${v// }"
    [ -n "$v" ] && d="$v"
  fi
  echo "$d"
}

host_dev_bootstrap() { echo "${ROOT}/scripts/host_dev_executor_bootstrap.py"; }
host_dev_log() { echo "${ROOT}/.runtime/host_dev_executor.log"; }
host_dev_pidf() { echo "${ROOT}/.runtime/host_dev_executor.pid"; }
web_log() { echo "${ROOT}/.runtime/nexa_web.log"; }
web_pidf() { echo "${ROOT}/.runtime/nexa_web.pid"; }

_wants_host_dev_from_env() {
  [ -f .env ] || return 1
  grep -qiE '^[[:space:]]*DEV_EXECUTOR_ON_HOST[[:space:]]*=(1|true|yes|on)([[:space:]]*#.*)?$' .env
}

# Called from ./run_everything.sh start (no zsh: avoids Cursor zsh + TERM=API tset/reset in the preexec).
stop_host_dev_executor() {
  local p pf
  pf="$(host_dev_pidf)"
  if [ -f "$pf" ]; then
    p=$(cat "$pf" 2>/dev/null) || p=""
    if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then
      echo "Stopping host dev executor (pid ${p})…" >&2
      kill "$p" 2>/dev/null || true
      i=0
      while kill -0 "$p" 2>/dev/null && [ "$i" -lt 30 ]; do sleep 0.2; i=$((i+1)) || true; done
    fi
    rm -f "$pf" 2>/dev/null || true
  fi
}

start_host_dev_executor_bg() {
  if [ "${RUN_EVERYTHING_NO_HOST_DEV:-0}" = "1" ]; then
    return 0
  fi
  if ! _wants_host_dev_from_env; then
    return 0
  fi
  warn_venv_if_host_dev_enabled
  local py
  if [ -x "${ROOT}/.venv/bin/python3" ]; then
    py="${ROOT}/.venv/bin/python3"
  else
    py="$(command -v python3 2>/dev/null || true)"
  fi
  if [ -z "$py" ]; then
    echo "warning: DEV_EXECUTOR_ON_HOST=1 in .env but no python3 — skipping host dev executor" >&2
    return 0
  fi
  mkdir -p "${ROOT}/.runtime"
  local b log pf old
  b="$(host_dev_bootstrap)"
  if [ ! -f "$b" ]; then
    echo "error: missing ${b}" >&2
    return 1
  fi
  log="$(host_dev_log)"
  pf="$(host_dev_pidf)"
  if [ -f "$pf" ] && [ -n "$(cat "$pf" 2>/dev/null)" ] && kill -0 "$(cat "$pf")" 2>/dev/null; then
    old="$(cat "$pf")"
    echo "host dev executor already running (pid ${old}); not starting another" >&2
    echo "  log:  ${log}"
    return 0
  fi
  # Non-interactive bash: no $BASH_ENV tset/reset; python is first in the nohup chain
  (
    cd "$ROOT" || exit 1
    nohup /usr/bin/env -u BASH_ENV -u ENV SHELL="/bin/sh" TERM="xterm-256color" \
      "$py" "$b" >>"$log" 2>&1 &
    echo $! >"$pf"
  ) || {
    echo "error: could not start host dev executor" >&2
    return 1
  }
  {
    local np
    np=$(cat "$pf" 2>/dev/null) || true
    echo "Host dev executor started (background, pid ${np}, DEV_EXECUTOR_ON_HOST=1)"
    echo "  log:  ${log}"
    echo "  view:  tail -f ${log}"
    echo "  (also stopped with: ./run_everything.sh stop)"
  } >&2
}

stop_web_dev() {
  local p pf
  pf="$(web_pidf)"
  if [ -f "$pf" ]; then
    p=$(cat "$pf" 2>/dev/null) || p=""
    if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then
      echo "Stopping Nexa web (npm, pid ${p})…" >&2
      kill "$p" 2>/dev/null || true
      i=0
      while kill -0 "$p" 2>/dev/null && [ "$i" -lt 30 ]; do sleep 0.2; i=$((i+1)) || true; done
    fi
    rm -f "$pf" 2>/dev/null || true
  fi
}

start_web_dev_bg() {
  if [ "${RUN_EVERYTHING_NO_WEB:-0}" = "1" ]; then
    return 0
  fi
  if [ ! -f "${ROOT}/web/package.json" ]; then
    echo "warning: web/package.json missing — skip Nexa web UI" >&2
    return 0
  fi
  if ! command -v npm &>/dev/null; then
    echo "warning: npm not found — skip Nexa web UI" >&2
    return 0
  fi
  mkdir -p "${ROOT}/.runtime"
  local log pf
  log="$(web_log)"
  pf="$(web_pidf)"
  if [ -f "$pf" ] && [ -n "$(cat "$pf" 2>/dev/null)" ] && kill -0 "$(cat "$pf")" 2>/dev/null; then
    local old
    old="$(cat "$pf")"
    echo "Nexa web (npm run dev) already running (pid ${old}); not starting another" >&2
    echo "  log:  ${log}" >&2
    return 0
  fi
  if [ ! -d "${ROOT}/web/node_modules" ]; then
    echo "Installing web dependencies (first run: cd web && npm install)…" >&2
    (cd "${ROOT}/web" && npm install) || {
      echo "error: npm install in web/ failed" >&2
      return 1
    }
  fi
  (
    cd "${ROOT}/web" || exit 1
    nohup /usr/bin/env -u BASH_ENV -u ENV SHELL="/bin/sh" TERM="xterm-256color" \
      npm run dev >>"$log" 2>&1 &
    echo $! >"$pf"
  ) || {
    echo "error: could not start Nexa web" >&2
    return 1
  }
  {
    local np
    np=$(cat "$pf" 2>/dev/null) || true
    echo "Nexa web UI: http://localhost:3000  (pid ${np}, log: ${log})"
    echo "  (stopped with: ./run_everything.sh stop)"
  } >&2
}

print_stack_urls() {
  local base="http://localhost:8010"
  local pgp
  pgp=$(published_pg_port)
  echo ""
  echo "── Local services (from your machine) ──"
  echo "  Backend / health     ${base}/api/v1/health"
  echo "  API docs (Swagger)   ${base}/docs"
  echo "  ReDoc                ${base}/redoc"
  echo "  Dashboard            ${base}/dashboard"
  echo "  Web UI (Next)        http://localhost:3000  (if started by run_everything)"
  echo "  Mission Control      http://localhost:3000/mission-control"
  echo "  Trust & activity     http://localhost:3000/trust"
  if [ "$IS_SQLITE_STACK" = "1" ]; then
    echo "  Database (SQLite)   file inside container (no host Postgres port)"
  else
    echo "  PostgreSQL (host)   localhost:${pgp}  →  container db:5432"
  fi
  echo "  Telegram bot         in Docker; chat in the Telegram app (no local URL)"
  echo ""
  echo "  In-process (API container / uvicorn — no extra daemon):"
  echo "    • Check-in follow-ups (APScheduler, followup_poll_seconds)"
  echo "    • Operator cycle → dev jobs / local_tool_worker when enabled (OPERATOR_POLL_SECONDS)"
  echo "-----------------------------------------"
  echo ""
}

# Extra steps that are NOT started by this script — only documented here so approval / host flows make sense.
print_permission_flow_hints() {
  echo ""
  echo "── Permissions, Web approve, host jobs ──"
  echo "  ./run_everything.sh stop | start is enough to start/stop processes — if flows are missing,"
  echo "  check configuration (same .env Docker loads), not extra shell commands:"
  echo ""
  echo "  • Web UI (inline permission cards + POST …/permissions/…/approve): open http://localhost:3000"
  echo "    In the app, set identity (tg_<TelegramUserId>) so /api/v1/web/chat can authenticate."
  echo "    If npm/web did not start: install Node/npm, run once: (cd web && npm install), or see web log:"
  echo "      $(web_log)"
  echo ""
  echo "  • Approved host-executor jobs (local_tool): picked up by the API process (container or native)"
  echo "    when OPERATOR_AUTO_RUN_LOCAL_TOOLS=true in .env (common default). No separate worker command."
  echo "    Paths like /Users/… must exist inside the API container unless you bind-mount them in docker-compose.yml"
  echo "    and set HOST_EXECUTOR_WORK_ROOT accordingly."
  echo ""
  if _wants_host_dev_from_env; then
    echo "  • DEV_EXECUTOR_ON_HOST=1 in .env — this script starts the host dev executor loop (see log:"
    echo "      $(host_dev_log)  ). That loop runs dev-agent tasks on the Mac, not a substitute for local_tool in Docker."
  else
    echo "  • Optional Mac-side loop: set DEV_EXECUTOR_ON_HOST=1 in .env (see env.docker.example); then"
    echo "    re-run ./run_everything.sh start so the script starts scripts/host_dev_executor_bootstrap.py."
  fi
  echo "-----------------------------------------"
  echo ""
}

case "${1:-}" in
  help|-h|--help)
    sed -n '1,35p' "$0"
    exit 0
    ;;
  stop|down)
    echo "Stopping stack…"
    stop_web_dev
    stop_host_dev_executor
    if [ -x "${ROOT}/scripts/stop_operator_stack.sh" ]; then
      "${ROOT}/scripts/stop_operator_stack.sh" || true
    fi
    if [ "$NATIVE_STACK" != "1" ]; then
      dc down
    else
      echo "Native stack: host API/bot stopped (no Docker to stop)."
    fi
    exit 0
    ;;
  status|ps)
    if [ "$NATIVE_STACK" = "1" ]; then
      echo "=== Native stack (pids in .runtime/) ==="
      for f in api.pid bot.pid; do
        p="${ROOT}/.runtime/$f"
        if [ -f "$p" ]; then echo "  $f: $(cat "$p" 2>/dev/null) (pid file)"; fi
      done
      echo "=== Docker (if any) ==="
      command -v docker &>/dev/null && docker info &>/dev/null && docker compose "${COMPOSE_ARGS[@]}" ps 2>/dev/null || true
    else
      dc ps
    fi
    exit 0
    ;;
  logs)
    shift || true
    if [ "$NATIVE_STACK" = "1" ]; then
      echo "Native logs: tail -f ${ROOT}/.runtime/api.log ${ROOT}/.runtime/bot.log  $(web_log)" >&2
      exit 0
    fi
    dc logs -f "${@:-}"
    exit 0
    ;;
  build)
    shift || true
    if [ "$NATIVE_STACK" = "1" ]; then
      echo "error: native mode has no image build. Use: ./run_everything.sh build (from repo root, Docker)" >&2
      exit 1
    fi
    dc build "$@"
    exit 0
    ;;
esac

if [ "$NATIVE_STACK" != "1" ]; then
  if ! command -v docker &>/dev/null; then
    echo "error: docker not found. Install Docker Desktop and ensure the daemon is running." >&2
    exit 1
  fi
  if ! docker info &>/dev/null; then
    echo "error: Docker daemon not reachable. Start Docker Desktop (or the docker service) and try again." >&2
    exit 1
  fi
  if ! docker compose version &>/dev/null; then
    echo "error: 'docker compose' (v2) not found. Use Docker with Compose v2." >&2
    exit 1
  fi
fi

# Env: prefer Docker-specific template, then the generic one
if [ ! -f .env ]; then
  if [ -f env.docker.example ]; then
    cp env.docker.example .env
    echo "Created .env from env.docker.example — set TELEGRAM_BOT_TOKEN and any API keys, then re-run or restart."
  elif [ -f .env.example ]; then
    cp .env.example .env
    echo "Created .env from .env.example — for Docker+Postgres, prefer copying env.docker.example to .env and adjusting."
  else
    echo "error: no .env. Create it from env.docker.example (or .env.example)." >&2
    exit 1
  fi
fi

if [ -f .env ] && [ "${TELEGRAM_CHECK:-1}" = "1" ]; then
  if ! grep -qE '^[[:space:]]*TELEGRAM_BOT_TOKEN=[^[:space:]]+' .env 2>/dev/null; then
    echo "warning: TELEGRAM_BOT_TOKEN is missing or empty in .env — the bot container will fail until you set a token." >&2
  fi
fi

DETACH=0
NO_WATCH=0
while [ "${1:-}" != "" ]; do
  case "$1" in
    --detach|-d) DETACH=1; shift ;;
    --no-watch) NO_WATCH=1; shift ;;
    --help|-h)
      sed -n '1,35p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done
[ "$START_ALWAYS" = "1" ] && DETACH=1

# Native stack: host .venv + scripts/start_operator_stack.sh (no Docker). Same optional web + host dev executor.
if [ "$NATIVE_STACK" = "1" ]; then
  if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
    echo "error: native stack requires ${ROOT}/.venv — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
  fi
  if [[ ! -x "${ROOT}/scripts/start_operator_stack.sh" ]]; then
    echo "error: missing ${ROOT}/scripts/start_operator_stack.sh" >&2
    exit 1
  fi
  echo "Starting native stack (uvicorn + Telegram bot on this machine; reads ${ROOT}/.env)…"
  "${ROOT}/scripts/start_operator_stack.sh"
  wait_api_healthy || true
  start_host_dev_executor_bg || true
  start_web_dev_bg || true
  print_stack_urls
  echo ""
  echo "── Native process logs ──"
  echo "  API:  ${ROOT}/.runtime/api.log"
  echo "  Bot:  ${ROOT}/.runtime/bot.log"
  echo "  Web:  $(web_log)"
  echo "Stop:  ./run_everything.sh native stop   (./run_everything.sh stop also stops host API/bot and Docker)"
  print_permission_flow_hints
  exit 0
fi

# Compose watch: build, start, then watch filesystem (see docker-compose.yml develop.watch)
has_watch=0
if [ "$NO_WATCH" = 0 ] && [ "$DETACH" = 0 ]; then
  if docker compose watch --help &>/dev/null; then
    has_watch=1
  fi
fi

if [ "$DETACH" = "1" ]; then
  echo "Starting stack in background: ${COMPOSE_ARGS[*]}"
  dc up -d --build
  wait_api_healthy || true
  print_stack_urls
  echo "This stack stays up until you run ./run_everything.sh stop (or Docker is stopped):"
  echo "  · Telegram bot — long-polling, replies in-app"
  echo "  · API — runs operator on OPERATOR_POLL_SECONDS; dev executor when OPERATOR_AUTO_RUN_DEV_EXECUTOR=true (see .env)"
  echo "  · job handoff / check-in nudges — use follow-up poll in the API + bot (see followup/operator settings)"
  echo ""
  echo "Running containers:"
  dc ps
  start_host_dev_executor_bg
  start_web_dev_bg || true
  print_permission_flow_hints
  echo "Logs: ./run_everything.sh logs   (add USE_SQLITE=1 for the SQLite stack)"
  echo "Web UI log:  $(web_log)   (disable web: RUN_EVERYTHING_NO_WEB=1)"
  exit 0
fi

if [ "$has_watch" = 1 ] && [ "$NO_WATCH" = 0 ]; then
  echo "Starting stack with file watch (rebuild on requirements/Dockerfile, sync+restart on app/ & scripts/)…"
  print_stack_urls
  start_web_dev_bg || true
  echo "Web UI log:  $(web_log)   (disable: RUN_EVERYTHING_NO_WEB=1)"
  echo "Ctrl+C stops watch (containers may keep running; use ./run_everything.sh stop)"
  exec docker compose "${COMPOSE_ARGS[@]}" watch
else
  if [ "$NO_WATCH" = 0 ]; then
    echo "Note: 'docker compose watch' not available or you passed --no-watch. Running one-shot up (rebuild to pick up code changes)." >&2
  fi
  print_stack_urls
  start_web_dev_bg || true
  echo "Web UI log:  $(web_log)   (disable: RUN_EVERYTHING_NO_WEB=1)"
  exec docker compose "${COMPOSE_ARGS[@]}" up --build
fi

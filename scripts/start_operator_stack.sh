#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV_BIN="${ROOT}/.venv/bin"
PY="${VENV_BIN}/python"
UVICORN="${VENV_BIN}/uvicorn"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
RUNTIME_DIR="${ROOT}/.runtime"
API_LOG="${RUNTIME_DIR}/api.log"
BOT_LOG="${RUNTIME_DIR}/bot.log"
API_PID_FILE="${RUNTIME_DIR}/api.pid"
BOT_PID_FILE="${RUNTIME_DIR}/bot.pid"
HEALTH_URL="http://${HOST}:${PORT}/api/v1/health"

mkdir -p "$RUNTIME_DIR"

if [[ ! -x "$PY" || ! -x "$UVICORN" ]]; then
  echo "error: .venv is missing required executables. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

stop_pid_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  fi
}

stop_pid_file "$API_PID_FILE"
stop_pid_file "$BOT_PID_FILE"
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "app.bot.telegram_bot" 2>/dev/null || true
sleep 1

nohup "$UVICORN" app.main:app --host "$HOST" --port "$PORT" >>"$API_LOG" 2>&1 &
echo $! > "$API_PID_FILE"

nohup "$PY" -m app.bot.telegram_bot >>"$BOT_LOG" 2>&1 &
echo $! > "$BOT_PID_FILE"

sleep 3

api_pid="$(cat "$API_PID_FILE" 2>/dev/null || true)"
bot_pid="$(cat "$BOT_PID_FILE" 2>/dev/null || true)"

if [[ -z "$api_pid" ]] || ! kill -0 "$api_pid" 2>/dev/null; then
  echo "error: API failed to stay running. See $API_LOG" >&2
  tail -n 40 "$API_LOG" >&2 || true
  exit 1
fi

if [[ -z "$bot_pid" ]] || ! kill -0 "$bot_pid" 2>/dev/null; then
  echo "error: Bot failed to stay running. See $BOT_LOG" >&2
  tail -n 60 "$BOT_LOG" >&2 || true
  exit 1
fi

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "error: API process is up but health check failed at $HEALTH_URL" >&2
  tail -n 40 "$API_LOG" >&2 || true
  exit 1
fi

echo "API started on $HOST:$PORT (pid $(cat "$API_PID_FILE"))"
echo "Bot started (pid $(cat "$BOT_PID_FILE"))"
echo "Logs:"
echo "  $API_LOG"
echo "  $BOT_LOG"

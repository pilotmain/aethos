#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ROOT}/.runtime"
API_PID_FILE="${RUNTIME_DIR}/api.pid"
BOT_PID_FILE="${RUNTIME_DIR}/bot.pid"

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
echo "Operator stack stopped."

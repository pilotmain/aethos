#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ROOT}/.runtime"
API_PID_FILE="${RUNTIME_DIR}/api.pid"
BOT_PID_FILE="${RUNTIME_DIR}/bot.pid"

show_pid() {
  local label="$1"
  local file="$2"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "$label: running (pid $pid)"
      return
    fi
  fi
  echo "$label: not running"
}

show_pid "API" "$API_PID_FILE"
show_pid "Bot" "$BOT_PID_FILE"

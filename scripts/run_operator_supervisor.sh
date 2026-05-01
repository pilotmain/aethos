#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUNTIME_DIR="${ROOT}/.runtime"
SUPERVISOR_LOG="${RUNTIME_DIR}/supervisor.log"
CHECK_INTERVAL="${OPERATOR_SUPERVISOR_INTERVAL:-15}"

mkdir -p "$RUNTIME_DIR"

echo "$(date '+%Y-%m-%d %H:%M:%S') operator supervisor starting" >>"$SUPERVISOR_LOG"

while true; do
  if ! ./scripts/operator_stack_status.sh | grep -q "not running"; then
    sleep "$CHECK_INTERVAL"
    continue
  fi

  echo "$(date '+%Y-%m-%d %H:%M:%S') restarting operator stack" >>"$SUPERVISOR_LOG"
  if ! ./scripts/start_operator_stack.sh >>"$SUPERVISOR_LOG" 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') restart attempt failed" >>"$SUPERVISOR_LOG"
  fi
  sleep "$CHECK_INTERVAL"
done

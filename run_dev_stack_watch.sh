#!/usr/bin/env bash
# Watch app code (and a few other paths) and restart the full dev stack on every change.
# Uses `watchfiles` (ships with `uvicorn[standard]` in this venv) so the Telegram bot
# also reloads; plain `uvicorn --reload` only restarts the API, not the bot.
#
# Usage: ./run_dev_stack_watch.sh
#   PORT=9000 ./run_dev_stack_watch.sh   # custom API port
#
# Ctrl+C stops the watcher and the child processes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV_BIN="${ROOT}/.venv/bin"
WATCH="${VENV_BIN}/watchfiles"
PORT="${PORT:-8000}"
export PORT

if [[ ! -x "$WATCH" ]]; then
  echo "error: watchfiles not found at $WATCH. Install: .venv/bin/pip install 'uvicorn[standard]'" >&2
  exit 1
fi
if [[ ! -x "${VENV_BIN}/uvicorn" ]]; then
  echo "error: .venv missing. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

echo "[watch] project: $ROOT"
echo "[watch] on change → bash run_dev_stack.sh  (PORT=$PORT)"
echo

# --filter default: ignores __pycache__, .pyc, .venv, etc. (unlike --filter all, which would restart on every bytecode write)
WATCH_PATHS=(
  "${ROOT}/app"
  "${ROOT}/scripts"
  "${ROOT}/run_dev_stack.sh"
  "${ROOT}/run.sh"
)
# Restart when env changes (if present)
if [[ -f "${ROOT}/.env" ]]; then
  WATCH_PATHS+=("${ROOT}/.env")
fi

exec "$WATCH" \
  --target-type command \
  --filter default \
  --grace-period 0.35 \
  "bash ${ROOT}/run_dev_stack.sh" \
  "${WATCH_PATHS[@]}"

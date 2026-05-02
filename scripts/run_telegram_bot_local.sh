#!/usr/bin/env bash
# Run the Telegram bot with the same DB override as ./scripts/nexa_next_local_all.sh:
# NEXA_NEXT_LOCAL_SIDECAR=1 forces repo-root SQLite when .env points at Postgres that is not running.
#
# Usage (from anywhere):
#   ./scripts/run_telegram_bot_local.sh
#
# Or: use the project venv explicitly:
#   NEXA_NEXT_LOCAL_SIDECAR=1 /path/to/nexa-next/.venv/bin/python -m app.bot.telegram_bot
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export NEXA_NEXT_LOCAL_SIDECAR=1
PY="${ROOT}/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "error: expected venv at ${PY} (create: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)" >&2
  exit 1
fi
exec "$PY" -m app.bot.telegram_bot

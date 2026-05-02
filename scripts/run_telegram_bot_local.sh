#!/usr/bin/env bash
# Run the Telegram bot with SQLite sidcar (NEXA_NEXT_LOCAL_SIDECAR=1) so Postgres does not need to be up.
# For Docker Postgres + host DATABASE_URL: ./scripts/docker_postgres_up.sh then either
#   NEXA_NEXT_LOCAL_SIDECAR=0 .venv/bin/python -m app.bot.telegram_bot
# or simply ./scripts/nexa_next_local_all.sh start (auto-starts db when .env is Postgres and Docker exists).
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

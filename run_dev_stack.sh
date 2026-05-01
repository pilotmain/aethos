#!/usr/bin/env bash
# Nexa: kill stale API/bot, show LLM settings, start Uvicorn + Telegram bot.
# Prereq: .env in project root with at least:
#   USE_REAL_LLM=true
#   ANTHROPIC_API_KEY=...   (and/or OPENAI_API_KEY=...)
#   TELEGRAM_BOT_TOKEN=...  (for the bot)
#
# Optional: LLM_PROVIDER=anthropic
#
# Usage: from project root
#   chmod +x run_dev_stack.sh
#   ./run_dev_stack.sh
#
# Port: API on 8000 (override: PORT=9000 ./run_dev_stack.sh)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV_BIN="${ROOT}/.venv/bin"
PORT="${PORT:-8000}"
PY="${VENV_BIN}/python"
UVICORN="${VENV_BIN}/uvicorn"

if [[ ! -x "$PY" ]]; then
  echo "error: .venv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

echo "[run_dev_stack] working directory: $ROOT"

if [[ ! -f "${ROOT}/.env" ]]; then
  echo "warning: .env not found in project root. Copy .env.example to .env and set keys." >&2
fi

echo "[run_dev_stack] stopping old uvicorn / telegram_bot processes (if any)..."
pkill -f "app.bot.telegram_bot" 2>/dev/null || true
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

echo
# If .env literally says false, that overrides everything (common gotcha).
if [[ -f "${ROOT}/.env" ]] && grep -qE '^[[:space:]]*USE_REAL_LLM[[:space:]]*=[[:space:]]*([Ff][Aa][Ll][Ss][Ee]|0)' "${ROOT}/.env"; then
  echo "warning: ${ROOT}/.env sets USE_REAL_LLM to false. Change the line to: USE_REAL_LLM=true" >&2
fi
# Quick sanity checks (each process also prints === SETTINGS DEBUG === on startup)
if ! "$PY" -c "import sys; from app.core.config import get_settings; sys.exit(0 if get_settings().use_real_llm else 1)"; then
  echo "warning: USE_REAL_LLM is off after loading .env. Fix the line in .env (unquoted: USE_REAL_LLM=true) and save." >&2
fi

if ! "$PY" -c "import sys; from app.core.config import get_settings; s=get_settings(); sys.exit(0 if (s.anthropic_api_key or s.openai_api_key) else 1)"; then
  echo "warning: set ANTHROPIC_API_KEY and/or OPENAI_API_KEY in .env" >&2
fi

cleanup() {
  if [[ -n "${UVICORN_PID:-}" ]] && kill -0 "$UVICORN_PID" 2>/dev/null; then
    echo "[run_dev_stack] stopping uvicorn (pid $UVICORN_PID)..."
    kill "$UVICORN_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo
echo "[run_dev_stack] starting API on 0.0.0.0:$PORT (background)..."
"$UVICORN" app.main:app --reload --host 0.0.0.0 --port "$PORT" &
UVICORN_PID=$!

# Give the API a moment to bind; lifespan runs === SETTINGS DEBUG === in app/main.py
sleep 1

echo
echo "[run_dev_stack] starting Telegram bot (foreground). Ctrl+C stops the bot, then the script stops uvicorn."
echo
"$PY" -m app.bot.telegram_bot
STATUS=$?
exit "$STATUS"

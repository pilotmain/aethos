#!/usr/bin/env bash
# Align local API port with the web UI default (8010) and smoke-test auth endpoints.
# Usage: from repo root, ./scripts/fix_api_connection.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

UVICORN="${ROOT}/.venv/bin/uvicorn"
if [[ ! -x "$UVICORN" ]]; then
  echo "Missing $UVICORN — create .venv and install deps first."
  exit 1
fi

echo "Stopping existing app.main uvicorn (if any)..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"

PORT="${NEXA_FIX_API_PORT:-8010}"
echo "Starting API on http://0.0.0.0:${PORT} (override with NEXA_FIX_API_PORT=8000)..."
"$UVICORN" app.main:app --reload --host 0.0.0.0 --port "${PORT}" &
API_PID=$!
sleep 4

echo "Health:"
curl -sS -o /dev/null -w "  %{http_code}\n" "http://127.0.0.1:${PORT}/api/v1/health" || true

echo ""
echo "Gateway run (raw-only JSON — must not 422):"
curl -sS -o /tmp/_gw.json -w "  %{http_code}\n" \
  -X POST "http://127.0.0.1:${PORT}/api/v1/mission-control/gateway/run" \
  -H "Content-Type: application/json" \
  -d "{\"raw\":\"ping\",\"user_id\":\"contract_test_user\"}" || true
head -c 200 /tmp/_gw.json 2>/dev/null || true
echo ""

echo ""
echo "Done. PID ${API_PID}"
echo "Set Mission Control → Connection → API base to: http://127.0.0.1:${PORT}"
echo "Match NEXA_WEB_API_TOKEN / X-User-Id in the UI if the API requires bearer auth."

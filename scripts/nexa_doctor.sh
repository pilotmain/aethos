#!/usr/bin/env bash
# Phase 54 — operator diagnostic: install_check + compose status + quick health + bot logs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Nexa doctor ==="
echo ""

bash "${ROOT}/scripts/install_check.sh" || true
echo ""

if command -v docker >/dev/null 2>&1 && [ -f "${ROOT}/docker-compose.yml" ]; then
  echo "--- docker compose ps ---"
  docker compose -f "${ROOT}/docker-compose.yml" ps 2>/dev/null || echo "(compose ps unavailable)"
  echo ""
fi

API_BASE="${API_BASE_URL:-http://127.0.0.1:8010}"
echo "--- curl ${API_BASE%/}/api/v1/health ---"
if command -v curl >/dev/null 2>&1; then
  curl -fsS --max-time 3 "${API_BASE%/}/api/v1/health" 2>/dev/null || echo "(API not reachable)"
else
  echo "(curl missing)"
fi
echo ""

if command -v docker >/dev/null 2>&1 && [ -f "${ROOT}/docker-compose.yml" ]; then
  echo "--- docker compose logs bot --tail=50 ---"
  docker compose -f "${ROOT}/docker-compose.yml" logs bot --tail=50 2>/dev/null || echo "(no bot service or logs)"
fi

echo ""
echo "Next: fix any warnings above, then ./scripts/install_check.sh --fix if .env is missing."

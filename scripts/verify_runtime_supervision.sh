#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Live runtime supervision verification (Phase 4 Step 19).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API="${AETHOS_API_URL:-${NEXA_API_BASE:-http://127.0.0.1:8010}}"
API="${API%/}"

echo "AethOS Runtime Supervision Check"
echo "================================"

api_owner="unknown"
sqlite_st="unknown"
telegram_st="unknown"
hydration_st="unknown"
dup_api="unknown"
mc_st="unknown"

if command -v aethos >/dev/null 2>&1; then
  own_line="$(aethos runtime ownership 2>/dev/null | head -1 || true)"
  if echo "$own_line" | grep -qi "active"; then
    api_owner="healthy"
  elif echo "$own_line" | grep -qi "none"; then
    api_owner="observer"
  else
    api_owner="check"
  fi
  svc="$(aethos runtime services 2>/dev/null || true)"
  if echo "$svc" | grep -q "API processes: 0"; then
    api_owner="stopped"
  fi
  if echo "$svc" | grep -q "API processes: [2-9]"; then
    dup_api="detected"
  else
    dup_api="none"
  fi
  if echo "$svc" | grep -qi "embedded"; then
    telegram_st="embedded in API"
  elif echo "$svc" | grep -q "Telegram bots: 0"; then
    telegram_st="inactive"
  else
    telegram_st="standalone"
  fi
else
  api_owner="aethos CLI not in PATH"
fi

if curl -sf "${API}/api/v1/runtime/db-health" >/dev/null 2>&1; then
  sqlite_st="healthy"
else
  sqlite_st="degraded"
fi

if curl -sf "${API}/api/v1/runtime/startup-lock" | grep -q '"holder_pid": null'; then
  hydration_st="clear"
else
  hydration_st="held or unknown"
fi

if curl -sf "${API}/api/v1/health" >/dev/null 2>&1; then
  mc_st="reachable"
else
  mc_st="unreachable"
fi

for port in 8000 8010 3000; do
  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port ${port}: listening"
  fi
done

echo "API owner: ${api_owner}"
echo "SQLite: ${sqlite_st}"
echo "Telegram: ${telegram_st}"
echo "Hydration lock: ${hydration_st}"
echo "Duplicate API processes: ${dup_api}"
echo "Mission Control API: ${mc_st}"

if [[ "$dup_api" == "detected" || "$sqlite_st" == "degraded" || "$mc_st" == "unreachable" ]]; then
  exit 2
fi
exit 0

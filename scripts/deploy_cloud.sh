#!/usr/bin/env bash
# Deploy AethOS Cloud stack (Docker Compose). Schema is ensured by API startup (ensure_schema), not Alembic.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Deploying AethOS Cloud from ${ROOT}..."

if [[ -d .git ]]; then
  git pull origin main || true
fi

docker compose -f docker-compose.cloud.yml build
docker compose -f docker-compose.cloud.yml up -d

API_HEALTH="${API_HEALTH:-http://localhost:8000/api/v1/health}"
sleep 10
curl -fsS "$API_HEALTH" >/dev/null

echo "AethOS Cloud is up (health OK: ${API_HEALTH})."

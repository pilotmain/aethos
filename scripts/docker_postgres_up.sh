#!/usr/bin/env bash
# Start only the Postgres service from docker-compose.yml (host port from POSTGRES_HOST_PORT in .env).
#
# Use this before running the API or Telegram bot on the host with:
#   DATABASE_URL=postgresql+psycopg2://overwhelm:overwhelm@127.0.0.1:<port>/overwhelm
#
#   ./scripts/docker_postgres_up.sh
#
# Same as: (cd repo && docker compose up -d db)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ ! -f docker-compose.yml ]; then
  echo "error: docker-compose.yml not found in ${ROOT}" >&2
  exit 1
fi
if ! command -v docker &>/dev/null; then
  echo "error: docker not installed or not in PATH" >&2
  exit 1
fi

echo "Starting Docker service 'db' (postgres:16-alpine, container nexa-db) …"
docker compose up -d db

_pg_port="5433"
if [ -f "${ROOT}/.env" ]; then
  line="$(grep -E '^[[:space:]]*POSTGRES_HOST_PORT=' "${ROOT}/.env" 2>/dev/null | tail -1 || true)"
  if [ -n "${line:-}" ]; then
    _pg_port="${line#*=}"
    _pg_port="${_pg_port// /}"
    _pg_port="${_pg_port//\"/}"
    _pg_port="${_pg_port//\'/}"
  fi
fi
export POSTGRES_HOST_PORT="${_pg_port}"

echo "Waiting for 127.0.0.1:${POSTGRES_HOST_PORT} …"
for _i in $(seq 1 60); do
  if command -v nc &>/dev/null && nc -z 127.0.0.1 "${POSTGRES_HOST_PORT}" 2>/dev/null; then
    echo "Postgres is accepting connections on host port ${POSTGRES_HOST_PORT}."
    echo "Host DATABASE_URL (matches docker-compose db credentials):"
    echo "  postgresql+psycopg2://overwhelm:overwhelm@127.0.0.1:${POSTGRES_HOST_PORT}/overwhelm"
    docker compose ps db
    exit 0
  fi
  sleep 1
done
echo "error: Postgres did not become reachable on 127.0.0.1:${POSTGRES_HOST_PORT} (see: docker compose logs db)" >&2
exit 1

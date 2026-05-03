#!/usr/bin/env bash
# Phase 54 — verify local prerequisites, ports, and optional service health.
# Run from repo root: ./scripts/install_check.sh  [--json] [--quiet] [--fix]
# --fix: only when .env is missing, copy from .env.example (non-destructive).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

JSON=0
QUIET=0
FIX=0
for arg in "$@"; do
  case "$arg" in
    --json) JSON=1 ;;
    --quiet) QUIET=1 ;;
    --fix) FIX=1 ;;
    *) ;;
  esac
done

say() { [ "$QUIET" = 1 ] && [ "$JSON" = 0 ] && return 0; printf '%s\n' "$*"; }
warn() { say "check: $*"; }
fail_msg=""

JSONL="${ROOT}/.runtime/install_check.jsonl"
push_json_item() {
  local status="$1" code="$2" msg="$3"
  if [ "$JSON" = 1 ]; then
    mkdir -p "${ROOT}/.runtime"
    python3 -c "import json,sys; print(json.dumps({'status':sys.argv[1],'code':sys.argv[2],'message':sys.argv[3]}))" "$status" "$code" "$msg" >>"${JSONL}"
  fi
}

rm -f "${JSONL:-}"
EXIT=0

check_fail() {
  EXIT=1
  fail_msg="$1"
  push_json_item "fail" "$2" "$1"
}

check_warn() {
  push_json_item "warn" "$2" "$1"
  warn "$1"
}

check_ok() {
  push_json_item "ok" "$2" "$1"
  say "ok: $1"
}

if ! command -v python3 >/dev/null 2>&1; then
  check_fail "python3 missing" "python3"
fi
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
  check_fail "Python 3.10+ required" "python_version"
fi

if ! command -v node >/dev/null 2>&1; then
  check_warn "node not in PATH (optional for web build)" "node"
else
  check_ok "node present" "node"
fi

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    check_ok "docker running" "docker"
  else
    check_warn "docker present but not running" "docker"
  fi
else
  check_warn "docker not in PATH" "docker"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  check_ok "docker compose available" "compose"
else
  check_warn "docker compose not available" "compose"
fi

[ -d "${ROOT}/.venv" ] || check_warn "no .venv (create venv + pip install -r requirements.txt)" "venv"

if [ ! -f "${ROOT}/.env" ]; then
  if [ "$FIX" = 1 ] && [ -f "${ROOT}/.env.example" ]; then
    cp "${ROOT}/.env.example" "${ROOT}/.env"
    check_ok "created .env from .env.example (--fix)" "env_created"
  else
    check_warn "no .env (copy from .env.example or run with --fix)" "env"
  fi
else
  check_ok ".env present" "env"
fi

if [ -f "${ROOT}/.env" ] && grep -qE '^[[:space:]]*TELEGRAM_BOT_TOKEN[[:space:]]*=' "${ROOT}/.env" 2>/dev/null; then
  :
else
  check_warn "TELEGRAM_BOT_TOKEN not set in .env (optional)" "telegram_token"
fi

port_note() {
  local port="$1"
  if command -v nc >/dev/null 2>&1; then
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then
      check_ok "port ${port} listening" "port_${port}"
    else
      check_warn "port ${port} not listening (start stack if expected)" "port_${port}"
    fi
  else
    check_warn "nc not available; skipped port ${port} check" "port_${port}"
  fi
}

for port in 3120 8010 5434; do
  port_note "$port"
done

API_BASE="${API_BASE_URL:-http://127.0.0.1:8010}"
HEALTH="${API_BASE%/}/api/v1/health"
if command -v curl >/dev/null 2>&1; then
  if curl -fsS --max-time 2 "$HEALTH" >/dev/null 2>&1; then
    check_ok "API health reachable (${HEALTH})" "api_health"
  else
    check_warn "API health not reachable (${HEALTH})" "api_health"
  fi
  if curl -fsS --max-time 2 "http://127.0.0.1:3120/" >/dev/null 2>&1; then
    check_ok "web root reachable (127.0.0.1:3120)" "web_health"
  else
    check_warn "web not reachable on 127.0.0.1:3120" "web_health"
  fi
else
  check_warn "curl not installed; skipped HTTP checks" "curl"
fi

if command -v docker >/dev/null 2>&1 && [ -f "${ROOT}/docker-compose.yml" ]; then
  if docker compose -f "${ROOT}/docker-compose.yml" ps --status running -q 2>/dev/null | head -1 | grep -q .; then
    if docker compose -f "${ROOT}/docker-compose.yml" logs bot --tail 5 2>/dev/null | grep -q .; then
      check_ok "docker compose bot logs readable" "bot_logs"
    else
      check_warn "could not read bot logs (service name may differ)" "bot_logs"
    fi
  else
    check_warn "docker compose stack not running" "compose_ps"
  fi
fi

if [ "$JSON" = 1 ]; then
  mkdir -p "${ROOT}/.runtime"
  python3 -c "
import json, pathlib
root = pathlib.Path('$ROOT')
p = root / '.runtime' / 'install_check.jsonl'
rows = []
if p.is_file():
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
out = {'status': 'ok' if int('$EXIT') == 0 else 'fail', 'checks': rows}
print(json.dumps(out))
" 2>/dev/null || echo '{"status":"fail","checks":[]}'
  rm -f "${JSONL}"
  exit "$EXIT"
fi

if [ "$EXIT" = 0 ]; then
  say "install_check: done."
else
  say "install_check: completed with issues (${fail_msg:-see warnings})."
fi
exit "$EXIT"

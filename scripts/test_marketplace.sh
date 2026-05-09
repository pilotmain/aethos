#!/usr/bin/env bash
#
# Smoke-test Marketplace + Agent Assignment APIs + orchestration @mentions against a running API.
#
# Requires: curl, jq; Python 3 for safe .env parsing (non-interactive, no sourcing).
#
# Usage (from repo root):
#   ./scripts/test_marketplace.sh
#
# Environment:
#   NEXA_TEST_API_BASE   API origin (default: http://127.0.0.1:8010)
#   NEXA_WEB_API_TOKEN   Optional override (else read from repo-root .env safely)
#   TEST_X_USER_ID       Required web user id (e.g. tg_8272800795), unless set in .env as NEXA_TEST_X_USER_ID
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "error: need Python 3 (.venv/bin/python or python3) for safe .env parsing" >&2
  exit 2
fi

command -v curl >/dev/null 2>&1 || {
  echo "error: curl is required" >&2
  exit 2
}
command -v jq >/dev/null 2>&1 || {
  echo "error: jq is required" >&2
  exit 2
}

# Read a single KEY=value from .env without sourcing (handles optional quotes; ignores comments).
read_dotenv_value() {
  local key="$1"
  local envfile="${2:-$ROOT/.env}"
  "$PYTHON_BIN" -c "
import sys
key, path = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding='utf-8') as f:
        for raw in f:
            line = raw.split('#', 1)[0].strip()
            if not line or '=' not in line:
                continue
            k, val = line.split('=', 1)
            if k.strip() != key:
                continue
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in '\"':
                val = val[1:-1]
            print(val)
            sys.exit(0)
except OSError:
    pass
sys.exit(1)
" "$key" "$envfile" 2>/dev/null || true
}

API_BASE="${NEXA_TEST_API_BASE:-http://127.0.0.1:8010}"
API_BASE="${API_BASE%/}"
API_V1="$API_BASE/api/v1"

TOKEN="${NEXA_WEB_API_TOKEN:-}"
if [[ -z "$TOKEN" && -f "$ROOT/.env" ]]; then
  TOKEN="$(read_dotenv_value NEXA_WEB_API_TOKEN "$ROOT/.env")"
fi

USER_ID="${TEST_X_USER_ID:-}"
if [[ -z "$USER_ID" && -f "$ROOT/.env" ]]; then
  USER_ID="$(read_dotenv_value NEXA_TEST_X_USER_ID "$ROOT/.env")"
fi
if [[ -z "$USER_ID" ]]; then
  echo "error: set TEST_X_USER_ID (or NEXA_TEST_X_USER_ID in .env) to a valid web user id" >&2
  exit 2
fi

HDRS=(-H "X-User-Id: $USER_ID" -H "Accept: application/json")
if [[ -n "${TOKEN:-}" ]]; then
  HDRS+=(-H "Authorization: Bearer $TOKEN")
fi

FAILURES=0
pass() { echo "ok  $*"; }
fail() { echo "FAIL $*" >&2; FAILURES=$((FAILURES + 1)); }

expect_http_json() {
  local name="$1"
  local want="$2"
  shift 2
  local tmp code body
  tmp="$(mktemp "${TMPDIR:-/tmp}/nexa_smoke.XXXXXX")"
  code="$(curl -sS -o "$tmp" -w "%{http_code}" "$@")"
  body="$(cat "$tmp")"
  rm -f "$tmp"
  if [[ "$code" != "$want" ]]; then
    fail "$name: HTTP $code (want $want) body=${body:0:200}"
    return 1
  fi
  printf '%s' "$body"
}

# --- Health ---
code="$(curl -sS -o /dev/null -w "%{http_code}" "${HDRS[@]}" "$API_V1/health")"
if [[ "$code" != "200" ]]; then
  fail "GET /health -> HTTP $code (is API running at $API_BASE?)"
fi
pass "GET /health"

rs_tmp="$(mktemp "${TMPDIR:-/tmp}/nexa_rs.XXXXXX")"
rs_code="$(curl -sS -o "$rs_tmp" -w "%{http_code}" "${HDRS[@]}" "$API_V1/marketplace/-/registry-status")"
rs_json="$(cat "$rs_tmp")"
rm -f "$rs_tmp"
if [[ "$rs_code" == "200" ]] && echo "$rs_json" | jq -e '.ok == true' >/dev/null 2>&1; then
  pass "GET marketplace/-/registry-status"
else
  fail "GET marketplace/-/registry-status HTTP $rs_code"
fi

# --- Marketplace (read) ---
SKILL_NAME=""
search_body="$(expect_http_json "GET marketplace/search" "200" "${HDRS[@]}" "$API_V1/marketplace/search?q=skill&limit=5")" || true
if [[ "$(echo "$search_body" | jq -r '.ok // false')" == "true" ]]; then
  SKILL_NAME="$(echo "$search_body" | jq -r '.skills[0].name // empty')"
  pass "GET marketplace/search"
else
  fail "GET marketplace/search json .ok"
fi

alias_body="$(expect_http_json "GET marketplace/skills/search (alias)" "200" "${HDRS[@]}" "$API_V1/marketplace/skills/search?q=test&limit=3")" || true
if [[ "$(echo "$alias_body" | jq -r '.ok // false')" == "true" ]]; then
  pass "GET marketplace/skills/search"
else
  fail "GET marketplace/skills/search"
fi

for path in "popular?limit=5" "featured?limit=5" "categories" "installed" "-/capabilities"; do
  b="$(expect_http_json "GET marketplace/$path" "200" "${HDRS[@]}" "$API_V1/marketplace/$path")" || continue
  if [[ "$(echo "$b" | jq -r '.ok // false')" == "true" ]]; then
    pass "GET marketplace/$path"
  else
    fail "GET marketplace/$path (.ok)"
  fi
done

if [[ -n "$SKILL_NAME" ]]; then
  enc="$(printf '%s' "$SKILL_NAME" | jq -sRr @uri)"
  info="$(expect_http_json "GET marketplace/skill/{name}" "200" "${HDRS[@]}" "$API_V1/marketplace/skill/$enc")" || true
  if echo "$info" | jq -e '.ok == true' >/dev/null 2>&1; then
    pass "GET marketplace/skill/$SKILL_NAME"
  else
    fail "GET marketplace/skill/$SKILL_NAME"
  fi
  det="$(expect_http_json "GET marketplace/skill/{name}/details" "200" "${HDRS[@]}" "$API_V1/marketplace/skill/$enc/details")" || true
  if echo "$det" | jq -e '.ok == true' >/dev/null 2>&1; then
    pass "GET marketplace/skill/$SKILL_NAME/details"
  else
    fail "GET marketplace/skill/$SKILL_NAME/details"
  fi
else
  pass "GET marketplace/skill/* (skipped — search returned no skills)"
fi

# --- Marketplace (mutating): endpoint reachable (403 owner gate or 404 missing is OK) ---
probe_owner_post() {
  local label="$1"
  local url="$2"
  shift 2
  local code
  code="$(curl -sS -o /dev/null -w "%{http_code}" "$@" "$url")"
  if [[ "$code" == "200" || "$code" == "403" || "$code" == "404" || "$code" == "409" ]]; then
    pass "$label (HTTP $code)"
  else
    fail "$label -> HTTP $code"
  fi
}

probe_owner_post "POST marketplace/install" "$API_V1/marketplace/install" "${HDRS[@]}" \
  -H "Content-Type: application/json" -d '{"name":"__nexa_cli_probe__","version":"latest","force":false}'
probe_owner_post "POST marketplace/uninstall/{name}" "$API_V1/marketplace/uninstall/__nexa_cli_probe__" "${HDRS[@]}" -X POST
probe_owner_post "POST marketplace/update/{name}" "$API_V1/marketplace/update/__nexa_cli_probe__" "${HDRS[@]}" -X POST
probe_owner_post "POST marketplace/check-updates (alias)" "$API_V1/marketplace/check-updates" "${HDRS[@]}" -X POST
probe_owner_post "POST marketplace/-/check-updates-now" "$API_V1/marketplace/-/check-updates-now" "${HDRS[@]}" -X POST

# --- Agent assignments ---
alist="$(expect_http_json "GET agent-assignments" "200" "${HDRS[@]}" "$API_V1/agent-assignments")" || true
if echo "$alist" | jq -e '.assignments | type == "array"' >/dev/null 2>&1; then
  pass "GET agent-assignments"
else
  fail "GET agent-assignments"
fi

TS="$(date +%s)"
ASSIGN_BODY="$(cat <<EOF
{
  "assigned_to_handle": "research-analyst",
  "title": "cli smoke $TS",
  "description": "scripts/test_marketplace.sh",
  "auto_dispatch": false
}
EOF
)"
assign_tmp="$(mktemp "${TMPDIR:-/tmp}/nexa_assign.XXXXXX")"
assign_code="$(curl -sS -o "$assign_tmp" -w "%{http_code}" "${HDRS[@]}" -H "Content-Type: application/json" \
  -d "$ASSIGN_BODY" "$API_V1/agent-assignments")"
assign_json="$(cat "$assign_tmp")"
rm -f "$assign_tmp"
if [[ "$assign_code" == "200" ]] && echo "$assign_json" | jq -e '.id // .assignment_id' >/dev/null 2>&1; then
  pass "POST agent-assignments (explicit handle)"
else
  fail "POST agent-assignments explicit -> HTTP $assign_code body=${assign_json:0:240}"
fi

# Legacy-shaped body (agent_id + task) — schema coercion when registry has the id
spw_tmp="$(mktemp "${TMPDIR:-/tmp}/nexa_spw.XXXXXX")"
spw_code="$(curl -sS -o "$spw_tmp" -w "%{http_code}" "${HDRS[@]}" -H "Content-Type: application/json" \
  -d "{\"name\":\"cli_legacy_$TS\",\"domain\":\"qa\",\"skills\":[\"status\"]}" \
  "$API_V1/agents/spawn")"
spawn_json="$(cat "$spw_tmp")"
rm -f "$spw_tmp"
LEGACY_ID=""
if [[ "$spw_code" == "200" ]]; then
  LEGACY_ID="$(echo "$spawn_json" | jq -r '.agent.id // empty')"
fi
if [[ -n "$LEGACY_ID" ]]; then
  leg_tmp="$(mktemp "${TMPDIR:-/tmp}/nexa_leg.XXXXXX")"
  leg_code="$(curl -sS -o "$leg_tmp" -w "%{http_code}" "${HDRS[@]}" -H "Content-Type: application/json" \
    -d "{\"agent_id\":\"$LEGACY_ID\",\"task\":\"cli legacy coercion $TS\",\"auto_dispatch\":false}" \
    "$API_V1/agent-assignments")"
  leg_json="$(cat "$leg_tmp")"
  rm -f "$leg_tmp"
  if [[ "$leg_code" == "200" ]]; then
    pass "POST agent-assignments (agent_id + task coercion)"
  else
    fail "POST agent-assignments legacy coercion HTTP $leg_code ${leg_json:0:200}"
  fi
else
  pass "POST agent-assignments legacy coercion (skipped — spawn did not return agent id)"
fi

# --- Orchestration @mention via gateway ---
SPAWN_NAME="cli_smoke_${TS}"
sp2_tmp="$(mktemp "${TMPDIR:-/tmp}/nexa_sp2.XXXXXX")"
sp2_code="$(curl -sS -o "$sp2_tmp" -w "%{http_code}" "${HDRS[@]}" -H "Content-Type: application/json" \
  -d "{\"name\":\"$SPAWN_NAME\",\"domain\":\"qa\",\"skills\":[\"status\"]}" \
  "$API_V1/agents/spawn")"
spawn2="$(cat "$sp2_tmp")"
rm -f "$sp2_tmp"
if [[ "$sp2_code" == "200" ]] && echo "$spawn2" | jq -e '.ok == true' >/dev/null 2>&1; then
  pass "POST agents/spawn ($SPAWN_NAME)"
  gw_tmp="$(mktemp "${TMPDIR:-/tmp}/nexa_gw.XXXXXX")"
  gw_code="$(curl -sS -o "$gw_tmp" -w "%{http_code}" -H "Content-Type: application/json" \
    -d "{\"raw\":\"@$SPAWN_NAME status\",\"user_id\":\"$USER_ID\"}" \
    "$API_V1/mission-control/gateway/run")"
  gw_json="$(cat "$gw_tmp")"
  rm -f "$gw_tmp"
  if [[ "$gw_code" != "200" ]]; then
    fail "POST mission-control/gateway/run mention -> HTTP $gw_code ${gw_json:0:200}"
  elif echo "$gw_json" | jq -e '.intent == "sub_agent_orchestration"' >/dev/null 2>&1; then
    pass "POST gateway/run @mention -> intent sub_agent_orchestration"
  else
    fail "POST gateway/run mention — intent=$(echo "$gw_json" | jq -c '.intent') expected sub_agent_orchestration"
  fi
elif [[ "$sp2_code" == "503" ]] || echo "$spawn2" | jq -r '.detail // empty' | grep -qi orchestration; then
  fail "POST agents/spawn — orchestration disabled (HTTP $sp2_code; set NEXA_AGENT_ORCHESTRATION_ENABLED=true on API)"
else
  fail "POST agents/spawn — HTTP $sp2_code $spawn2"
fi

if [[ "$FAILURES" -eq 0 ]]; then
  echo ""
  echo "All checks passed ($API_BASE)."
  exit 0
fi

echo "" >&2
echo "$FAILURES check(s) failed." >&2
exit 1

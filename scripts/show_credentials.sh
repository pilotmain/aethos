#!/usr/bin/env bash
# Print Mission Control connection values from repo .env (safe parse, no `export $(grep …)`).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "No .env in $ROOT — run ./scripts/setup.sh first."
  exit 1
fi

PY="${ROOT}/.venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

exec "$PY" -c '
from pathlib import Path

def load_env(p: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip().strip("\"").strip("\x27")
    return out

e = load_env(Path(".env"))
api = e.get("API_BASE_URL", "http://127.0.0.1:8010")
uid = e.get("TEST_X_USER_ID", e.get("AETHOS_SETUP_X_USER_ID", "(set TEST_X_USER_ID)"))
tok = e.get("NEXA_WEB_API_TOKEN", "")

def mask(t: str) -> str:
    if not t or t in ("(not set)",):
        return t
    if len(t) <= 24:
        return t
    return t[:24] + "…" + t[-8:]

CY = "\033[0;36m"
BD = "\033[1m"
YW = "\033[1;33m"
GN = "\033[0;32m"
RD = "\033[0;31m"
NC = "\033[0m"

print(f"{CY}{'━' * 58}{NC}")
print(f"{BD}AethOS connection (Mission Control){NC}")
print(f"{CY}{'━' * 58}{NC}")
print(f"  {BD}API base:{NC}     {api}")
print(f"  {BD}X-User-Id:{NC}    {uid}")
print(f"  {BD}Bearer token:{NC} {mask(tok)}")
print()

try:
    import urllib.request
    h = api.rstrip("/") + "/api/v1/health"
    req = urllib.request.Request(h)
    with urllib.request.urlopen(req, timeout=5) as r:
        ok = r.status == 200
except Exception:
    ok = False

if ok:
    print(f"  {GN}✓ GET /api/v1/health responds{NC}")
else:
    print(f"  {RD}✗ Health check failed (is the API running?){NC}")

print(f"\n{CY}{'━' * 58}{NC}")
print(f"{BD}Host executor (autonomous runs){NC}")
nex = (e.get("NEXA_HOST_EXECUTOR_ENABLED") or "").strip().lower()
wr = (e.get("HOST_EXECUTOR_WORK_ROOT") or e.get("NEXA_WORKSPACE_ROOT") or "").strip()
if nex in ("1", "true", "yes"):
    print(f"  {GN}✓ NEXA_HOST_EXECUTOR_ENABLED{NC}")
    print(f"  {BD}HOST_EXECUTOR_WORK_ROOT:{NC} {wr or '(unset)'}")
else:
    print(f"  {YW}⚠ Host executor disabled — agents only return plans/code until you enable it.{NC}")

print(f"\n{YW}Keep NEXA_WEB_API_TOKEN secret.{NC}")
print(f"{CY}{'━' * 58}{NC}")
'

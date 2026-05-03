#!/usr/bin/env bash
# Phase 53 — verify local prerequisites and ports for Nexa-next (no mutation).
# Run from repo root: ./scripts/install_check.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ERR=0
warn() { echo "check: $*" >&2; }
fail() { echo "fail: $*" >&2; ERR=1; }

command -v python3 >/dev/null 2>&1 || fail "python3 missing"
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" || fail "Python 3.10+ required"

if command -v docker >/dev/null 2>&1; then
  docker info >/dev/null 2>&1 || warn "docker present but not running (optional)"
else
  warn "docker not in PATH (optional for compose stack)"
fi

[ -d "${ROOT}/.venv" ] || warn "no .venv (create: python3 -m venv .venv && pip install -r requirements.txt)"
[ -f "${ROOT}/.env" ] || warn "no .env (copy from .env.example)"
if [ -f "${ROOT}/.env" ] && grep -qE '^[[:space:]]*TELEGRAM_BOT_TOKEN[[:space:]]*=' "${ROOT}/.env" 2>/dev/null; then
  :
else
  warn "TELEGRAM_BOT_TOKEN not set in .env (bot optional)"
fi

# Typical local ports (adjust if you override env)
for port in 3120 8010 5434; do
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" 2>/dev/null && echo "port ${port}: listening" || echo "port ${port}: not listening (start stack if expected)"
  fi
done

if [ "$ERR" -eq 0 ]; then
  echo "install_check: done (see warnings above for optional items)."
else
  exit 1
fi

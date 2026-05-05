#!/usr/bin/env bash
# Phase 36 — Rebrand helper (Nexa → AethOS). Prefer tracked repo edits via git; do not blind-replace URLs.
#
# This script prints verification commands and optional greps. For environment migration see:
#   python scripts/migrate_env_aethos.py --dry-run
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "AethOS rebrand — verification (from repo root)"
echo ""
echo "1) Python env aliases load (AETHOS_* → NEXA_* before Settings):"
echo "   python -c \"from app.core.aethos_env import apply_aethos_env_aliases; apply_aethos_env_aliases(); print('ok')\""
echo ""
echo "2) CLI entrypoints:"
echo "   pip install -e . && aethos status && nexa status   # nexa is a compatibility alias"
echo ""
echo "3) Health JSON app name:"
echo "   curl -s \"\${AETHOS_API_BASE:-http://127.0.0.1:8010}/api/v1/health\" | python -m json.tool"
echo ""
echo "4) Search for leftover product string \"Nexa\" (excluding obvious repo URL nexa-next):"
echo "   rg '\\bNexa\\b' app web aethos_cli aethos-mobile docs --glob '!**/node_modules/**' || true"
echo ""

#!/usr/bin/env bash
# Phase 10 — run tests then provider isolation scanner.
set -euo pipefail
cd "$(dirname "$0")/.."
pytest "$@"
python scripts/verify_no_direct_providers.py

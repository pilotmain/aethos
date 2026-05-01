#!/usr/bin/env bash
# Phase 17 — tests, provider isolation, import contracts, integrity gate, Ruff.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pytest "$@"
python scripts/verify_no_direct_providers.py

if [[ -x "${ROOT}/.venv/bin/lint-imports" ]]; then
  "${ROOT}/.venv/bin/lint-imports" --config "${ROOT}/importlinter.ini"
elif command -v lint-imports >/dev/null 2>&1; then
  lint-imports --config "${ROOT}/importlinter.ini"
else
  echo "lint-imports not found; install import-linter (see requirements.txt)" >&2
  exit 1
fi

python scripts/system_integrity_check.py

if [[ -x "${ROOT}/.venv/bin/ruff" ]]; then
  "${ROOT}/.venv/bin/ruff" check app/
elif command -v ruff >/dev/null 2>&1; then
  ruff check app/
else
  echo "ruff not found; install dev deps (see requirements.txt)" >&2
  exit 1
fi

#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run the dedicated product E2E pytest slice (see tests/e2e/test_product_e2e_suite.py).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .venv/bin/pytest ]]; then
  echo "Missing .venv/bin/pytest — create venv and pip install -r requirements.txt" >&2
  exit 1
fi
exec .venv/bin/pytest tests/e2e/test_product_e2e_suite.py -m product_e2e "$@"

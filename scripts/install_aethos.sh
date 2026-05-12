#!/usr/bin/env bash
# Internal installer — delegates to the colorful setup wizard (scripts/setup.py via setup.sh).
#
#   bash scripts/install_aethos.sh
#   NEXA_USE_CURRENT_REPO=1 bash scripts/install_aethos.sh   # same tree when run from scripts/

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
exec bash ./scripts/setup.sh "$@"

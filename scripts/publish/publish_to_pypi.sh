#!/usr/bin/env bash
# Publish aethos-core to PyPI (run after aethos-core is split and public).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CORE_DIR="${REPO_ROOT}/../aethos-core"

if [[ ! -d "${CORE_DIR}" ]]; then
  echo "Expected aethos-core checkout at: ${CORE_DIR}" >&2
  exit 1
fi

cd "${CORE_DIR}"
python -m build
python -m twine upload dist/*

echo "Published to PyPI (if upload succeeded)."
echo "Install with: pip install aethos-core"

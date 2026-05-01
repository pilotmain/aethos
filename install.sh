#!/usr/bin/env bash
# Thin wrapper so you can run ./install.sh from the repo root after clone.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${ROOT}/scripts/install.sh" --no-clone "$@"

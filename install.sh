#!/usr/bin/env bash
# Thin wrapper — forwards all arguments to scripts/install.sh (Phase 55/56 bootstrap).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${HERE}/scripts/install.sh" "$@"

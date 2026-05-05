#!/usr/bin/env bash
# Deprecated installer name — forwards to scripts/install_aethos.sh (Phase 36).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "install_nexa_next_native.sh is deprecated — use install_aethos.sh" >&2
exec bash "${SCRIPT_DIR}/install_aethos.sh" "$@"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET_FILE="${TARGET_DIR}/com.overwhelmreset.operator.plist"
TEMPLATE="${ROOT}/ops/com.overwhelmreset.operator.plist"

mkdir -p "$TARGET_DIR"
sed "s#__ROOT__#${ROOT}#g" "$TEMPLATE" > "$TARGET_FILE"

launchctl unload "$TARGET_FILE" 2>/dev/null || true
launchctl load "$TARGET_FILE"

echo "Installed and loaded launchd agent:"
echo "  $TARGET_FILE"
echo
echo "Manage it with:"
echo "  launchctl unload $TARGET_FILE"
echo "  launchctl load $TARGET_FILE"

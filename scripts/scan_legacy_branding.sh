#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Scan legacy branding references (Phase 4 Step 17).
set -euo pipefail

MODE="${1:---operator-facing}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_JSON="${ROOT}/.aethos/branding_scan.json"
OUT_TXT="${ROOT}/.aethos/branding_scan_summary.txt"

EXCLUDES=(
  --glob '!.git/**'
  --glob '!.venv/**'
  --glob '!node_modules/**'
  --glob '!.next/**'
  --glob '!.pytest_cache/**'
  --glob '!.agent_tasks/**'
  --glob '!legacy_branding_scan*.txt'
  --glob '!**/__pycache__/**'
)

PATTERNS=('Nexa' 'OpenClaw' 'ClawHub' 'OpenHub')
ALLOWED_PATHS=(
  'docs/OPENCLAW'
  'tests/test_openclaw'
  'README.md'
  'COMPATIBILITY_ALIAS'
  'FINAL_LEGACY_POLICY'
  'NEXA_'
)

mkdir -p "${ROOT}/.aethos"
: > "${OUT_TXT}"

count=0
for pat in "${PATTERNS[@]}"; do
  c=$(rg -n "${pat}" "${ROOT}" "${EXCLUDES[@]}" 2>/dev/null | wc -l | tr -d ' ')
  echo "${pat}: ${c}" >> "${OUT_TXT}"
  count=$((count + c))
done

echo "total_matches: ${count}" >> "${OUT_TXT}"
echo "{\"mode\": \"${MODE}\", \"total_matches\": ${count}}" > "${OUT_JSON}"

if [[ "${MODE}" == "--operator-facing" ]]; then
  # Nonzero if disallowed hits in operator paths (heuristic)
  bad=$(rg -n 'Nexa|ClawHub|OpenHub' "${ROOT}/web" "${ROOT}/aethos_cli" "${ROOT}/scripts/setup.py" "${ROOT}/install.sh" 2>/dev/null | wc -l | tr -d ' ')
  echo "operator_facing_hits: ${bad}" >> "${OUT_TXT}"
  if [[ "${bad}" -gt 50 ]]; then
    echo "WARN: operator-facing legacy references above threshold (${bad})" >&2
    exit 2
  fi
fi

cat "${OUT_TXT}"

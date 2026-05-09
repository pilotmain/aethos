#!/usr/bin/env bash
# Append AETHOS_OWNER_IDS to .env when missing, derived from TELEGRAM_OWNER_IDS (canonical tg_* ids).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo ".env not found at ${ROOT}/.env — nothing to update." >&2
  exit 1
fi

if grep -qE '^[[:space:]]*AETHOS_OWNER_IDS=' .env; then
  echo "AETHOS_OWNER_IDS already set in .env"
  exit 0
fi

raw=""
if line="$(grep -E '^[[:space:]]*TELEGRAM_OWNER_IDS=' .env | head -1)"; then
  raw="${line#*=}"
fi
if [[ -z "${raw//[$' \t\r\n']/}" ]] && line="$(grep -E '^[[:space:]]*NEXA_SELF_IMPROVEMENT_OWNER_ID=' .env | head -1)"; then
  raw="${line#*=}"
fi

raw="${raw//\"/}"
raw="${raw//\'/}"
raw="$(echo "${raw}" | xargs)"

if [[ -z "${raw}" ]]; then
  echo "No TELEGRAM_OWNER_IDS or NEXA_SELF_IMPROVEMENT_OWNER_ID found — add AETHOS_OWNER_IDS manually (comma-separated tg_* / web_* ids)." >&2
  exit 1
fi

out=""
IFS=',' read -ra PARTS <<< "${raw}"
for p in "${PARTS[@]}"; do
  p="$(echo "${p}" | xargs)"
  [[ -z "${p}" ]] && continue
  if [[ "${p}" =~ ^tg_ ]] || [[ "${p}" =~ ^web_ ]]; then
    canon="${p}"
  elif [[ "${p}" =~ ^[0-9]+$ ]]; then
    canon="tg_${p}"
  else
    canon="${p}"
  fi
  if [[ -n "${out}" ]]; then
    out+=",${canon}"
  else
    out="${canon}"
  fi
done

{
  echo ""
  echo "# Added by scripts/fix_owner_config.sh — canonical ids for Mission Control owner gate (see AETHOS_OWNER_IDS in .env.example)."
  echo "AETHOS_OWNER_IDS=${out}"
} >> .env

echo "Appended AETHOS_OWNER_IDS=${out} to .env"

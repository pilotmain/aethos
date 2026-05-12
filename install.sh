#!/usr/bin/env bash
# AethOS — one-curl installer
#
#   curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- --help
#
# Optional: NEXA_REPO_URL, NEXA_INSTALL_DIR (same defaults as below).

set -euo pipefail

REPO_URL="${NEXA_REPO_URL:-https://github.com/pilotmain/aethos.git}"
INSTALL_DIR="${NEXA_INSTALL_DIR:-${HOME}/.aethos}"

# When run from a real checkout (not piped oneliner), configure this tree.
if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != bash && "${BASH_SOURCE[0]}" != "-" ]]; then
  _here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "${_here}/scripts/setup.sh" && -f "${_here}/install.sh" ]]; then
    cd "${_here}"
    exec bash ./scripts/setup.sh "$@"
  fi
fi

if ! command -v git &>/dev/null; then
  echo "Error: git is required to clone AethOS." >&2
  exit 1
fi

echo "🚀 Installing AethOS…"

if [[ -e "${INSTALL_DIR}" ]] && [[ ! -f "${INSTALL_DIR}/scripts/setup.sh" ]]; then
  echo "Error: ${INSTALL_DIR} exists but is not an AethOS clone (missing scripts/setup.sh)." >&2
  echo "Remove it or set NEXA_INSTALL_DIR to another path." >&2
  exit 1
fi

if [[ ! -d "${INSTALL_DIR}" ]]; then
  mkdir -p "$(dirname "${INSTALL_DIR}")"
  GIT_TERMINAL_PROMPT=0 git clone --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
else
  echo "✓ AethOS already present at ${INSTALL_DIR}"
fi

cd "${INSTALL_DIR}"
exec bash ./scripts/setup.sh "$@"

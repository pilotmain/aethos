#!/usr/bin/env bash
# AethOS — one-curl installer
# Usage: curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash
#
# Optional: NEXA_REPO_URL, NEXA_INSTALL_DIR

set -e

REPO_URL="${NEXA_REPO_URL:-https://github.com/pilotmain/aethos.git}"
INSTALL_DIR="${NEXA_INSTALL_DIR:-${HOME}/.aethos}"

# When run from a checkout (not piped stdin), configure this tree — same wizard as one-curl.
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

echo "🚀 Installing AethOS..."

if [[ -e "${INSTALL_DIR}" ]] && [[ ! -f "${INSTALL_DIR}/scripts/setup.sh" ]]; then
  echo "Error: ${INSTALL_DIR} exists but is not an AethOS clone (missing scripts/setup.sh)." >&2
  exit 1
fi

if [[ ! -d "${INSTALL_DIR}" ]]; then
  mkdir -p "$(dirname "${INSTALL_DIR}")"
  GIT_TERMINAL_PROMPT=0 git clone --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
else
  echo "✓ AethOS already installed at ${INSTALL_DIR}"
  cd "${INSTALL_DIR}"
  if [[ -d .git ]]; then
    GIT_TERMINAL_PROMPT=0 git pull --ff-only 2>/dev/null || GIT_TERMINAL_PROMPT=0 git pull
  fi
fi

cd "${INSTALL_DIR}"
exec bash ./scripts/setup.sh "$@"

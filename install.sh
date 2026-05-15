#!/usr/bin/env bash
# AethOS — one-curl installer (rev 2026-05-15b)
# Usage: curl -fsSL https://cdn.jsdelivr.net/gh/pilotmain/aethos@main/install.sh | bash
#        (raw.githubusercontent.com may lag; jsDelivr tracks main within minutes)
#
# Optional: NEXA_REPO_URL, NEXA_INSTALL_DIR

set -e

REPO_URL="${NEXA_REPO_URL:-https://github.com/pilotmain/aethos.git}"
INSTALL_DIR="${NEXA_INSTALL_DIR:-${HOME}/.aethos}"

_aethos_install_is_piped() {
  [[ "${BASH_SOURCE[0]:-}" == "-" ]] || [[ "${BASH_SOURCE[0]:-}" == "bash" ]]
}

# Run from a checkout on disk — go straight to the interactive wizard.
if [[ -n "${BASH_SOURCE[0]:-}" ]] && ! _aethos_install_is_piped; then
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
  echo "⚠️  ${INSTALL_DIR} exists but is not a valid AethOS install (missing scripts/setup.sh)."
  echo "   Removing leftover directory and re-cloning…"
  rm -rf "${INSTALL_DIR}"
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

# Piped curl scripts can be CDN-stale — always run the on-disk wizard (never trust pipe body routing).
exec bash "${INSTALL_DIR}/scripts/setup.sh" "$@"

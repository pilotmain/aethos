#!/usr/bin/env bash
# AethOS — one-curl installer entry (repo root).
#
#   curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash -s -- --help
#
# When piped, this script clones pilotmain/aethos (unless already present), then runs
# scripts/install_aethos.sh. When run from a git checkout, it delegates to that script
# in the same tree (no second clone).
#
# Maintainer notes (vs a “three-package” doc):
# - Canonical install is this monorepo (API, bots, CLI). Optional Pro wheels / extra PyPI
#   indexes are not hard-coded; set NEXA_LICENSE_KEY and vendor index in .env when provided.
# - Private GitHub: use SSH or https://TOKEN@github.com/pilotmain/aethos.git in NEXA_REPO_URL.
# - Pretty URL: point https://aethos.ai/install → this raw URL once DNS exists.
#
set -euo pipefail

REPO_DEFAULT="https://github.com/pilotmain/aethos.git"
INSTALL_DEFAULT="${HOME}/.aethos"

usage() {
  cat <<EOF
AethOS installer

  curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash

Options (after bash -s --):

  --help, -h          Show this help
  --license KEY       Export NEXA_LICENSE_KEY for Pro / signed-license flows (optional)
  --dir PATH          Install directory (default: ${INSTALL_DEFAULT})

Environment (common):

  NEXA_REPO_URL       Git clone URL (default: ${REPO_DEFAULT})
  NEXA_INSTALL_DIR    Same as --dir
  NEXA_NONINTERACTIVE=1   No prompts (also auto when stdin is not a TTY)
  NEXA_EXISTING_ACTION=1|2|3|4   When install dir exists: 1=update 2=fresh 3=repair 4=cancel
EOF
}

LICENSE_KEY=""
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help | -h)
      usage
      exit 0
      ;;
    --license)
      LICENSE_KEY="${2:-}"
      shift 2
      ;;
    --dir)
      export NEXA_INSTALL_DIR="${2:-}"
      shift 2
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -n "${LICENSE_KEY}" ]]; then
  export NEXA_LICENSE_KEY="${LICENSE_KEY}"
fi

export NEXA_REPO_URL="${NEXA_REPO_URL:-$REPO_DEFAULT}"
export NEXA_INSTALL_DIR="${NEXA_INSTALL_DIR:-$INSTALL_DEFAULT}"

if [[ ! -t 0 ]]; then
  export NEXA_NONINTERACTIVE="${NEXA_NONINTERACTIVE:-1}"
  export NEXA_EXISTING_ACTION="${NEXA_EXISTING_ACTION:-1}"
fi

_inner_from_bash_source() {
  local _src="${BASH_SOURCE[0]:-}"
  local _dir
  if [[ -z "$_src" || "$_src" == bash || "$_src" == "-" ]]; then
    return 1
  fi
  _dir="$(cd "$(dirname "$_src")" && pwd)"
  if [[ -f "$_dir/scripts/install_aethos.sh" ]]; then
    exec bash "$_dir/scripts/install_aethos.sh" "${EXTRA_ARGS[@]}"
  fi
  return 1
}

if _inner_from_bash_source; then
  exit 0
fi

DEST="${NEXA_INSTALL_DIR}"

if ! command -v git &>/dev/null; then
  echo "Error: git is required to clone AethOS." >&2
  exit 1
fi

if [[ ! -f "${DEST}/aethos_cli/__main__.py" ]]; then
  if [[ -e "${DEST}" ]] && [[ ! -d "${DEST}/.git" ]]; then
    echo "Error: ${DEST} exists and is not a git checkout. Choose another path or remove it." >&2
    exit 1
  fi
  if [[ ! -d "${DEST}" ]]; then
    echo "Cloning ${NEXA_REPO_URL} → ${DEST}"
    mkdir -p "$(dirname "${DEST}")"
    GIT_TERMINAL_PROMPT=0 git clone --depth 1 "${NEXA_REPO_URL}" "${DEST}"
  fi
fi

exec bash "${DEST}/scripts/install_aethos.sh" "${EXTRA_ARGS[@]}"

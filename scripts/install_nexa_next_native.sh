#!/usr/bin/env bash
# Nexa Next — native installer (venv + pip + ``python -m nexa_cli setup``).
# Does not replace scripts/install.sh (Docker bootstrap). Use when you want repo nexa-next only:
#
#   curl -fsSL https://raw.githubusercontent.com/pilotmain/nexa-next/main/scripts/install_nexa_next_native.sh | bash
#   (Public repo only — private repos return 404 for unauthenticated raw URLs; git clone, then:)
#   git clone https://github.com/pilotmain/nexa-next.git && cd nexa-next && bash scripts/install_nexa_next_native.sh
#
# From checkout:
#   NEXA_USE_CURRENT_REPO=1 bash scripts/install_nexa_next_native.sh
#
set -euo pipefail

NEXA_REPO_URL="${NEXA_REPO_URL:-https://github.com/pilotmain/nexa-next.git}"
NEXA_INSTALL_DIR="${NEXA_INSTALL_DIR:-${HOME}/nexa-next}"
PYTHON="${PYTHON:-python3}"

SCRIPT_PATH=""
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [[ "${NEXA_USE_CURRENT_REPO:-}" == "1" ]] && [[ -n "$SCRIPT_PATH" ]] && [[ -f "$SCRIPT_PATH/../nexa_cli/__main__.py" ]]; then
  NEXA_INSTALL_DIR="$(cd "$SCRIPT_PATH/.." && pwd)"
  echo "Using current repo: $NEXA_INSTALL_DIR"
fi

if ! command -v "$PYTHON" &>/dev/null; then
  echo "Python 3 is required (3.10+ recommended)." >&2
  exit 1
fi

if ! "$PYTHON" - <<'PY' &>/dev/null
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  echo "Python 3.10+ required." >&2
  exit 1
fi

if [[ ! -d "${NEXA_INSTALL_DIR}/nexa_cli" ]] || [[ ! -f "${NEXA_INSTALL_DIR}/requirements.txt" ]]; then
  if ! command -v git &>/dev/null; then
    echo "git is required to clone the repository." >&2
    exit 1
  fi
  echo "Cloning ${NEXA_REPO_URL} -> ${NEXA_INSTALL_DIR}"
  git clone --depth 1 "${NEXA_REPO_URL}" "${NEXA_INSTALL_DIR}"
fi

cd "${NEXA_INSTALL_DIR}"

if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo ""
echo "Running interactive setup (writes .env in this repo)..."
python -m nexa_cli setup

echo ""
echo "Done."
echo "  cd ${NEXA_INSTALL_DIR}"
echo "  source .venv/bin/activate"
echo "  python -m nexa_cli serve          # API on http://127.0.0.1:8010 by default"

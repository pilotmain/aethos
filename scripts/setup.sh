#!/usr/bin/env bash
# AethOS Enterprise Setup — thin orchestration wrapper (canonical path).
# Public: curl -fsSL …/install.sh | bash
# Local recovery: bash scripts/setup.sh
#
# Delegates to: aethos setup (aethos_cli/setup_wizard.py + enterprise extensions)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${GREEN}Launching AethOS Enterprise Setup${NC}"
echo "  • Resume: aethos setup resume"
echo "  • Repair: aethos setup repair"
echo "  • Local / cloud / hybrid routing in the wizard"
echo "  • Mission Control auto-connection when complete"
echo ""

if ! command -v python3 &>/dev/null; then
  echo -e "${RED}Python 3 not found. Install Python 3.9+ and retry.${NC}"
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo -e "${YELLOW}Creating virtual environment (.venv)…${NC}"
  python3 -m venv .venv
  echo -e "${GREEN}✓${NC} .venv created"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip -q
if [[ -f requirements.txt ]]; then
  pip install -q -r requirements.txt
fi
pip install -q -e . 2>/dev/null || true

# Reattach TTY for piped one-curl so aethos setup can prompt interactively
if [[ ! -t 0 ]] && [[ -c /dev/tty ]]; then
  exec </dev/tty
fi

export NEXA_SETUP_FROM_INSTALLER=1
export AETHOS_SETUP_FROM_INSTALLER=1

if [[ "${AETHOS_SETUP_DRY_RUN:-}" == "1" ]]; then
  echo -e "${YELLOW}Dry run — would execute: aethos setup${NC}"
  exit 0
fi

if command -v aethos &>/dev/null; then
  exec aethos setup "$@"
fi
exec python -m aethos_cli setup "$@"

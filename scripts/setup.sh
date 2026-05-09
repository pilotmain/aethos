#!/usr/bin/env bash
# AethOS Beautiful Setup — launches scripts/setup.py inside .venv when present.
# Usage (from repo root): bash scripts/setup.sh   or   ./scripts/setup.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}AethOS setup wizard${NC}"

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

exec python3 scripts/setup.py "$@"

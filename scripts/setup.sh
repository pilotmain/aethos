#!/usr/bin/env bash
# AethOS Beautiful Setup — launches scripts/setup.py inside .venv when present.
# Usage (from repo root): bash scripts/setup.sh   or   ./scripts/setup.sh
#
# API + Mission Control (npm), HTTP health waits (60s), and optional browser open are handled in
# scripts/setup.py (step “Start API & Mission Control”). Use --no-browser or AETHOS_SETUP_NO_BROWSER=1
# to skip opening http://localhost:3000. Use --skip-playwright-browsers or AETHOS_SETUP_SKIP_PLAYWRIGHT_BROWSERS=1
# to skip downloading Playwright Chromium during the “Configure .env” step. Legal / TTY behavior is in setup.py.
#
# One-curl / home install: AETHOS_ONE_CURL=1 or an existing ~/.aethos/.env makes the wizard write
# ~/.aethos/.env (not repo-root .env). Override with AETHOS_SETUP_REPO_ENV=1. Optional: ./scripts/setup.sh --home-env
# Ollama: AETHOS_SETUP_SKIP_OLLAMA_BOOTSTRAP=1 skips ``ollama serve`` / ``ollama pull`` during Configure .env (CI / air-gapped).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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

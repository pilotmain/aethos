#!/usr/bin/env bash
# One-command local bootstrap: data dir, .env template, venv, deps, SQLite schema.
# Usage: bash scripts/setup_aethos.sh   (from anywhere)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🪐 AethOS — local setup"
echo ""

mkdir -p data

if [[ ! -f .env ]]; then
  echo "📝 Creating .env from defaults (SQLite + orchestration)…"
  cat > .env << EOF
APP_NAME=AethOS
APP_ENV=development

# Unified SQLite — API + Telegram bot default to ~/.aethos/data/aethos.db when DATABASE_URL is omitted.
# Uncomment to pin explicitly (three slashes after sqlite: for absolute host path):
# DATABASE_URL=sqlite:///${HOME}/.aethos/data/aethos.db

NEXA_AGENT_ORCHESTRATION_ENABLED=true
NEXA_AGENT_MAX_PER_CHAT=20

USE_REAL_LLM=false

NEXA_WORKSPACE_ROOT=${HOME}/aethos-workspace
HOST_EXECUTOR_WORK_ROOT=${HOME}/aethos-workspace

# TELEGRAM_BOT_TOKEN=
# NEXA_TELEGRAM_EMBED_WITH_API=true
EOF
  echo -e "${GREEN}✓${NC} wrote .env — edit API keys and TELEGRAM_BOT_TOKEN as needed"
else
  echo -e "${YELLOW}⚠${NC} .env already exists — not overwriting"
fi

if [[ ! -d .venv ]]; then
  echo "🐍 Creating virtual environment (.venv)…"
  python3 -m venv .venv
  echo -e "${GREEN}✓${NC} .venv created"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "📦 Installing Python dependencies…"
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -e . -q
echo -e "${GREEN}✓${NC} Dependencies installed (editable package)"

echo "🗄️ Initializing database schema…"
python -c "from app.core.db import ensure_schema; ensure_schema()" || {
  echo -e "${YELLOW}⚠${NC} ensure_schema failed — run from repo root with .venv active: aethos init-db"
  exit 1
}
echo -e "${GREEN}✓${NC} Database ready (default ~/.aethos/data/aethos.db if DATABASE_URL unset)"

echo ""
echo -e "${GREEN}✅ Setup complete.${NC}"
echo ""
echo "Start the API:    source .venv/bin/activate && aethos serve"
echo "Initialize DB:    aethos init-db"
echo "Web UI:           cd web && npm install && npm run dev"

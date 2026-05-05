#!/usr/bin/env bash
# Nexa Next — Phase 32 native installer (step-by-step UX + wizard steps 3–6).
#
#   curl -fsSL https://raw.githubusercontent.com/pilotmain/nexa-next/main/scripts/install_nexa_next_native.sh | bash
#
# Production short URL (when hosted): curl -fsSL https://nexa.ai/install | bash
#
# Private GitHub repo (403/404 on raw): clone with auth first, then:
#   NEXA_USE_CURRENT_REPO=1 bash scripts/install_nexa_next_native.sh
#
set -euo pipefail

NEXA_REPO_URL="${NEXA_REPO_URL:-https://github.com/pilotmain/nexa-next.git}"
NEXA_INSTALL_DIR="${NEXA_INSTALL_DIR:-${HOME}/.nexa}"
PYTHON="${PYTHON:-python3}"

SCRIPT_PATH=""
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [[ "${NEXA_USE_CURRENT_REPO:-}" == "1" ]] && [[ -n "$SCRIPT_PATH" ]] && [[ -f "$SCRIPT_PATH/../nexa_cli/__main__.py" ]]; then
  NEXA_INSTALL_DIR="$(cd "$SCRIPT_PATH/.." && pwd)"
  echo "Using current repo: $NEXA_INSTALL_DIR"
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

banner() {
  echo -e "${CYAN}"
  cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ███╗   ██╗███████╗██╗  ██╗ █████╗                                         ║
║   ████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗                                        ║
║   ██╔██╗ ██║█████╗   ╚███╔╝ ███████║                                        ║
║   ██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║                                        ║
║   ██║ ╚████║███████╗██╔╝ ██╗██║  ██║                                        ║
║   ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝                                        ║
║                                                                              ║
║                    Next-Gen AI Agent Framework                               ║
║                              v1.0.0                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
EOF
  echo -e "${NC}"
}

hr() { echo "└─────────────────────────────────────────────────────────────────────────────┘"; }

step_frame_top() {
  echo "┌─────────────────────────────────────────────────────────────────────────────┐"
  echo "│  $1"
  echo "├─────────────────────────────────────────────────────────────────────────────┤"
}

step_frame_bottom() { hr; echo ""; }

free_gb() {
  local path="${1:-.}"
  # Portable: df -k → KiB available in column 4 (GNU and BSD)
  if df -k "$path" &>/dev/null; then
    df -k "$path" | awk 'NR==2 {printf "%.1f", $4/1024/1024}'
  else
    echo "?"
  fi
}

banner

OS="$(uname -s 2>/dev/null || echo unknown)"
ARCH="$(uname -m 2>/dev/null || echo unknown)"
CHIP=""
if [[ "$OS" == "Darwin" ]]; then
  if [[ "$ARCH" == "arm64" ]]; then CHIP="Apple Silicon"; else CHIP="Intel"; fi
  ENV_LINE="macOS (${CHIP})"
elif [[ "$OS" == Linux ]]; then
  ENV_LINE="Linux (${ARCH})"
else
  ENV_LINE="${OS} (${ARCH})"
fi
echo -e "📍 Environment: ${GREEN}${ENV_LINE}${NC} ✅"
echo ""

# --- Step 1/6 ---
step_frame_top "Step 1/6: Checking prerequisites"
if ! command -v "$PYTHON" &>/dev/null; then
  echo -e "│  ${RED}✗${NC} Python 3 not found. Install 3.10+ from https://www.python.org/downloads/"
  hr
  exit 1
fi
PY_VER="$("$PYTHON" --version 2>&1 | cut -d' ' -f2)"
echo -e "│  ${GREEN}✓${NC} Python ${PY_VER} found"
if ! "$PYTHON" - <<'PY' &>/dev/null
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  echo -e "│  ${RED}✗${NC} Python 3.10+ required."
  hr
  exit 1
fi

if command -v git &>/dev/null; then
  echo -e "│  ${GREEN}✓${NC} Git found"
else
  echo -e "│  ${RED}✗${NC} Git not found — install Git to clone the repository."
  hr
  exit 1
fi

if command -v node &>/dev/null; then
  NV="$(node --version 2>/dev/null || echo "")"
  echo -e "│  ${GREEN}✓${NC} Node.js optional — ${NV}"
else
  echo -e "│  ${YELLOW}○${NC} Node.js not found (optional, for Next.js)"
fi

if command -v ollama &>/dev/null && ollama list &>/dev/null; then
  echo -e "│  ${GREEN}✓${NC} Ollama detected"
elif command -v ollama &>/dev/null; then
  echo -e "│  ${YELLOW}!${NC} Ollama installed but \`ollama list\` failed"
else
  echo -e "│  ${YELLOW}!${NC} Ollama not installed (optional, for local LLM)"
  if [[ "$OS" == Darwin ]]; then
    echo -e "│     ${DIM}→ Install with: brew install ollama${NC}"
  else
    echo -e "│     ${DIM}→ https://ollama.ai/download${NC}"
  fi
fi

if command -v docker &>/dev/null; then
  echo -e "│  ${GREEN}✓${NC} Docker CLI present (optional)"
fi
step_frame_bottom

# --- Step 2/6 ---
step_frame_top "Step 2/6: Choose installation directory"
echo "│  Default location:"
echo -e "│    ${CYAN}${NEXA_INSTALL_DIR}${NC}"
_DISK_ROOT="${NEXA_INSTALL_DIR}"
[[ -d "$_DISK_ROOT" ]] || _DISK_ROOT="$(dirname "$NEXA_INSTALL_DIR")"
[[ -d "$_DISK_ROOT" ]] || _DISK_ROOT="${HOME}"
FREE_GB="$(free_gb "$_DISK_ROOT" 2>/dev/null || echo "?")"
echo "│  Space needed: ~500 MB"
if [[ "$FREE_GB" != "?" ]]; then
  echo -e "│  Space available: ~${FREE_GB} GB ${GREEN}✅${NC}"
else
  echo "│  Space available: (could not detect)"
fi
echo "│"
echo "│  Press Enter to use default, or type a path:"
read -r -p "│  > " DIR_INPUT
if [[ -n "${DIR_INPUT:-}" ]]; then
  NEXA_INSTALL_DIR="${DIR_INPUT/#\~/${HOME}}"
fi
echo -e "│  ${GREEN}✓${NC} Using: ${NEXA_INSTALL_DIR}"
step_frame_bottom

export NEXA_SETUP_KIND=""
if [[ -d "${NEXA_INSTALL_DIR}/.git" ]] || [[ -f "${NEXA_INSTALL_DIR}/nexa_cli/__main__.py" ]]; then
  echo -e "${YELLOW}Existing Nexa directory detected.${NC}"
  echo "   [1] Update — git pull + configure"
  echo "   [2] Fresh — delete folder and clone again"
  echo "   [3] Repair — reinstall deps + configure"
  echo "   [4] Cancel"
  read -r -p "   > " EXIST_CHOICE
  case "${EXIST_CHOICE:-}" in
    1)
      export NEXA_SETUP_KIND="update"
      cd "${NEXA_INSTALL_DIR}"
      git pull --ff-only || git pull
      ;;
    2)
      export NEXA_SETUP_KIND="fresh"
      echo -e "${YELLOW}Removing ${NEXA_INSTALL_DIR}…${NC}"
      rm -rf "${NEXA_INSTALL_DIR}"
      if ! command -v git &>/dev/null; then
        echo "git is required to clone." >&2
        exit 1
      fi
      echo "Cloning ${NEXA_REPO_URL} → ${NEXA_INSTALL_DIR}"
      GIT_TERMINAL_PROMPT=0 git clone --depth 1 "${NEXA_REPO_URL}" "${NEXA_INSTALL_DIR}"
      ;;
    3)
      export NEXA_SETUP_KIND="repair"
      ;;
    *)
      echo "Cancelled."
      exit 0
      ;;
  esac
else
  export NEXA_SETUP_KIND="fresh"
  if ! command -v git &>/dev/null; then
    echo "git is required to clone the repository." >&2
    exit 1
  fi
  echo -e "${BLUE}Starting clone…${NC}"
  GIT_TERMINAL_PROMPT=0 git clone --depth 1 "${NEXA_REPO_URL}" "${NEXA_INSTALL_DIR}"
fi

cd "${NEXA_INSTALL_DIR}"

# --- Step 6/6 (install phase before interactive wizard) ---
step_frame_top "Step 6/6: Installing (clone / venv / dependencies)"
echo -e "│  ${GREEN}✓${NC} Repository ready at ${NEXA_INSTALL_DIR}"

if [[ ! -d .venv ]]; then
  echo "│  🐍 Creating virtual environment…"
  "$PYTHON" -m venv .venv
fi
echo -e "│  ${GREEN}✓${NC} Virtual environment: ${NEXA_INSTALL_DIR}/.venv"

# shellcheck disable=SC1091
source .venv/bin/activate

echo "│  📚 Upgrading pip & installing dependencies (may take a minute)…"
python -m pip install --upgrade pip --quiet
REQ_LINES="$(wc -l < requirements.txt | tr -d ' ')"
echo "│     (${REQ_LINES} requirement lines — compiling wheels can take several minutes)"
if python -m pip install -r requirements.txt; then
  echo -e "│  ${GREEN}✓${NC} Python packages installed"
else
  echo -e "│  ${RED}✗${NC} pip install failed — see messages above." >&2
  hr
  exit 1
fi
step_frame_bottom

echo ""
echo -e "${BLUE}🔧 Launching configuration wizard (steps 3–5 of 6: LLM, keys, features)…${NC}"
export NEXA_SETUP_FROM_INSTALLER=1
export NEXA_SETUP_KIND="${NEXA_SETUP_KIND:-fresh}"
python -m nexa_cli setup

echo ""
echo -e "${GREEN}Done.${NC} Activate later with: ${CYAN}cd ${NEXA_INSTALL_DIR} && source .venv/bin/activate${NC}"

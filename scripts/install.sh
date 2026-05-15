#!/usr/bin/env bash
# Nexa single-command bootstrap: clone (optional), venv + deps, .env, optional keys, DB schema, start stack.
#
# From an empty directory:
#   curl -fsSL https://pilotmain.com/install.sh | bash
#   (redirects to raw.githubusercontent.com/pilotmain/nexa/main/scripts/install.sh)
#
# Already in repo root:
#   ./scripts/install.sh --no-clone
#
# Environment (non-interactive / CI):
#   NEXA_REPO_URL       — git URL (default: https://github.com/pilotmain/nexa.git)
#   NEXA_DIR            — clone directory name (default: nexa)
#   ANTHROPIC_API_KEY, OPENAI_API_KEY, TELEGRAM_BOT_TOKEN — merged into .env when set
#   NEXA_START          — none | docker | host (default: host — no Docker)
#   PORT                — API port for host mode (default: 8000)
#   NEXA_NONINTERACTIVE — 1 to skip prompts (use env vars for keys)
#
set -euo pipefail

NEXA_REPO_URL="${NEXA_REPO_URL:-https://github.com/pilotmain/nexa.git}"
NEXA_DIR="${NEXA_DIR:-nexa}"
START_MODE="${NEXA_START:-}"
NONINTERACTIVE="${NEXA_NONINTERACTIVE:-0}"
SKIP_KEYS=0
NO_CLONE=0
DRY_RUN=0
GUIDED=0
BOOTSTRAP_ONLY=0
BOOTSTRAP_EXTRA=()

usage() {
  sed -n '1,25p' "$0"
  echo ""
  echo "Options:"
  echo "  --no-clone      Assume current directory is the Nexa repo root (or NEXA_ROOT)."
  echo "  --no-docker     Deprecated (Docker is off by default)."
  echo "  --force-env     Refresh .env from .env.example (keeps existing API keys/tokens)."
  echo "  --start MODE    none | docker | host (default: host)."
  echo "  --skip-keys     Do not prompt for API keys / Telegram token."
  echo "  --guided        Short interactive tour: OS hint, local-first, Telegram, then bootstrap."
  echo "  --bootstrap-only Skip the colorful setup wizard; run nexa_bootstrap + optional start."
  echo "  --dry-run       Print planned steps only (no bootstrap, no starts)."
  echo "  -h, --help      This help."
}

run_guided_intro() {
  echo ""
  echo "=== Nexa guided setup (Phase 55) ==="
  echo "Detected: $(uname -s) $(uname -m)"
  echo ""
  echo "Tip: for privacy-first runs, set NEXA_LOCAL_FIRST=true in .env (see docs/INSTALL.md)."
  echo ""
  if [ -t 0 ] && [ "${NONINTERACTIVE:-0}" != "1" ]; then
    read -r -p "Add Telegram bot token during key prompts? [y/N] " tg_yn || true
    case "${tg_yn:-}" in
      y|Y|yes|YES)
        echo "(You will be asked for TELEGRAM_BOT_TOKEN in the optional keys step.)"
        ;;
      *)
        echo "(Skipping Telegram — you can add TELEGRAM_BOT_TOKEN to .env later.)"
        ;;
    esac
    read -r -p "Open docs/SETUP.md when finished? [y/N] " doc_yn || true
    case "${doc_yn:-}" in
      y|Y|yes|YES)
        if command -v open >/dev/null 2>&1; then
          GUIDED_OPEN_DOC=1
        elif command -v xdg-open >/dev/null 2>&1; then
          GUIDED_OPEN_DOC=1
        else
          echo "Open ${ROOT}/docs/SETUP.md in your editor when ready."
        fi
        ;;
    esac
  fi
  echo ""
}

while [ "${1:-}" != "" ]; do
  case "$1" in
    --no-clone) NO_CLONE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --guided) GUIDED=1; shift ;;
    --bootstrap-only) BOOTSTRAP_ONLY=1; shift ;;
    --no-docker) shift ;;
    --force-env) BOOTSTRAP_EXTRA+=(--force-env); shift ;;
    --start)
      START_MODE="${2:-}"
      shift 2 || true
      ;;
    --skip-keys) SKIP_KEYS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

NONINTERACTIVE="${NEXA_NONINTERACTIVE:-0}"
SKIP_WIZARD="${AETHOS_SKIP_WIZARD:-0}"

die() { echo "error: $*" >&2; exit 1; }

# Default: full colorful interactive wizard (scripts/setup.py). Fast bootstrap only when opted in.
if [ "$BOOTSTRAP_ONLY" != 1 ] && [ "$DRY_RUN" != 1 ] && [ "$NONINTERACTIVE" != "1" ] && [ "$SKIP_WIZARD" != "1" ]; then
  _wizard_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [ -f "${_wizard_root}/scripts/setup.sh" ]; then
    exec bash "${_wizard_root}/scripts/setup.sh" "$@"
  fi
fi

# macOS / bash 3.2 + ``set -u``: ``"${arr[@]}"`` on an empty array is an unbound variable.
bootstrap_extra_contains() {
  local needle="$1"
  local item
  for item in "${BOOTSTRAP_EXTRA[@]}"; do
    if [ "$item" = "$needle" ]; then
      return 0
    fi
  done
  return 1
}

run_nexa_bootstrap() {
  if ((${#BOOTSTRAP_EXTRA[@]} > 0)); then
    python3 scripts/nexa_bootstrap.py "${BOOTSTRAP_EXTRA[@]}"
  else
    python3 scripts/nexa_bootstrap.py
  fi
}

command -v git >/dev/null 2>&1 || die "git is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" || die "Python 3.10+ required"

if [ "$NO_CLONE" = 1 ]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  cd "$ROOT"
else
  if [ -f scripts/nexa_bootstrap.py ]; then
    ROOT="$(pwd)"
  elif [ -f "${NEXA_DIR}/scripts/nexa_bootstrap.py" ]; then
    ROOT="$(cd "${NEXA_DIR}" && pwd)"
    cd "$ROOT"
  else
    echo "Cloning Nexa into ./${NEXA_DIR} ..."
    git clone "$NEXA_REPO_URL" "$NEXA_DIR"
    ROOT="$(cd "${NEXA_DIR}" && pwd)"
    cd "$ROOT"
  fi
fi

[ -f scripts/nexa_bootstrap.py ] || die "not the Nexa repo root: ${ROOT}"

if [ "$DRY_RUN" = 1 ]; then
  echo "[dry-run] Repository root: ${ROOT}"
  if ((${#BOOTSTRAP_EXTRA[@]} > 0)); then
    echo "[dry-run] Would run: python3 scripts/nexa_bootstrap.py ${BOOTSTRAP_EXTRA[*]}"
  else
    echo "[dry-run] Would run: python3 scripts/nexa_bootstrap.py"
  fi
  echo "[dry-run] Privacy-first defaults: set NEXA_LOCAL_FIRST=true and review docs/INSTALL.md before exposing keys."
  echo "[dry-run] Would merge keys from env when non-interactive (see merge_keys_from_env in script)."
  echo "[dry-run] No file changes, no services started. Re-run without --dry-run to apply."
  exit 0
fi

mkdir -p "${ROOT}/.runtime"

echo "=== Nexa install — repo: ${ROOT} ==="

if [ "$GUIDED" = 1 ]; then
  run_guided_intro
fi

echo "Running: python3 scripts/nexa_bootstrap.py ..."
run_nexa_bootstrap

merge_keys_from_env() {
  # Patch .env from exported variables (non-interactive).
  .venv/bin/python3 <<'PY'
from __future__ import annotations

import os
import re
from pathlib import Path

root = Path.cwd()
env_path = root / ".env"
if not env_path.is_file():
    raise SystemExit(0)

keys = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "USE_REAL_LLM",
]
extra = os.environ.get("NEXA_WEB_SEARCH_API_KEY")
text = env_path.read_text(encoding="utf-8")
changed = False
for k in keys:
    v = os.environ.get(k)
    if v is None or str(v).strip() == "":
        continue
    v = str(v).strip()
    pat = re.compile(rf"^{re.escape(k)}\s*=.*$", re.MULTILINE)
    if pat.search(text):
        text = pat.sub(f"{k}={v}", text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"{k}={v}\n"
    changed = True
if extra and str(extra).strip():
    k = "NEXA_WEB_SEARCH_API_KEY"
    v = str(extra).strip()
    pat = re.compile(rf"^{re.escape(k)}\s*=.*$", re.MULTILINE)
    if pat.search(text):
        text = pat.sub(f"{k}={v}", text)
    else:
        text += f"{k}={v}\n"
    # Enable search only when key provided (optional).
    for ek, ev in (
        ("NEXA_WEB_SEARCH_ENABLED", "true"),
        ("NEXA_WEB_SEARCH_PROVIDER", "tavily"),
    ):
        if not re.search(rf"^{re.escape(ek)}\s*=", text, re.MULTILINE):
            text += f"{ek}={ev}\n"
    changed = True

# If any LLM key is set, prefer real LLM when USE_REAL_LLM not forced
if (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")) and not os.environ.get("USE_REAL_LLM"):
    if not re.search(r"^USE_REAL_LLM\s*=", text, re.MULTILINE):
        text += "USE_REAL_LLM=true\n"
        changed = True

if changed:
    env_path.write_text(text, encoding="utf-8")
PY
}

prompt_keys() {
  if [ "$SKIP_KEYS" = 1 ] || [ "$NONINTERACTIVE" = "1" ]; then
    return 0
  fi
  if [ ! -t 0 ]; then
    return 0
  fi
  echo ""
  echo "Optional: add API keys now (press Enter to skip any line)."
  read -r -p "Anthropic API key (primary LLM): " ANTHROPIC_API_KEY || true
  read -r -p "OpenAI API key (fallback): " OPENAI_API_KEY || true
  read -r -p "Telegram bot token (optional, for the bot): " TELEGRAM_BOT_TOKEN || true
  export ANTHROPIC_API_KEY OPENAI_API_KEY TELEGRAM_BOT_TOKEN
  if [ -n "${ANTHROPIC_API_KEY:-}${OPENAI_API_KEY:-}" ]; then
    export USE_REAL_LLM="${USE_REAL_LLM:-true}"
  fi
}

if [ "$NONINTERACTIVE" != "1" ] && [ -t 0 ] && [ "$SKIP_KEYS" != 1 ]; then
  read -r -p "Enter API keys interactively now? [y/N] " keys_yn || true
  case "${keys_yn:-}" in
    y|Y|yes|YES) prompt_keys ;;
  esac
fi
if [ -x .venv/bin/python3 ]; then
  merge_keys_from_env
else
  echo "warning: skipping .env key merge (no .venv/bin/python3 yet)." >&2
fi

if [ ! -x .venv/bin/python3 ]; then
  echo "warning: .venv missing or incomplete; skipping schema check." >&2
else
  echo "Ensuring database schema (ensure_schema) ..."
  cd "$ROOT"
  .venv/bin/python3 -c "
from pathlib import Path
from app.services.nexa_bootstrap import repair_env_database_url
from app.core.config import get_settings
from app.core.db import ensure_schema

repair_env_database_url(Path('.').resolve())
get_settings.cache_clear()
ensure_schema()
" || echo "warning: ensure_schema failed — API startup will retry." >&2
fi

auto_start="${START_MODE:-${NEXA_START:-host}}"

start_docker() {
  command -v docker >/dev/null 2>&1 || die "Docker not installed"
  docker info >/dev/null 2>&1 || die "Docker daemon not running"
  chmod +x "${ROOT}/run_everything.sh" 2>/dev/null || true
  echo "Starting Docker stack (Postgres + API + bot + web when npm present) ..."
  bash "${ROOT}/run_everything.sh" start
}

start_host() {
  command -v npm >/dev/null 2>&1 || die "Node/npm required for web UI — install Node or use --start docker"
  chmod +x "${ROOT}/run_dev_stack.sh" 2>/dev/null || true
  PORT="${PORT:-8000}"
  echo "Starting API + web on host (SQLite default; API port ${PORT}) ..."
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  mkdir -p "${ROOT}/.runtime"
  nohup env -u BASH_ENV -u ENV SHELL="/bin/sh" TERM="${TERM:-xterm-256color}" \
    "${ROOT}/.venv/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port "${PORT}" \
    >>"${ROOT}/.runtime/install_api.log" 2>&1 &
  echo $! >"${ROOT}/.runtime/install_api.pid"
  if [ ! -d "${ROOT}/web/node_modules" ]; then
    (cd "${ROOT}/web" && npm install)
  fi
  nohup env -u BASH_ENV -u ENV SHELL="/bin/sh" TERM="${TERM:-xterm-256color}" \
    bash -c 'cd "$1" && npm run dev' bash "${ROOT}/web" \
    >>"${ROOT}/.runtime/install_web.log" 2>&1 &
  echo $! >"${ROOT}/.runtime/install_web.pid"
  echo ""
  echo "API log:  ${ROOT}/.runtime/install_api.log"
  echo "Web log:  ${ROOT}/.runtime/install_web.log"
  echo "API:      http://127.0.0.1:${PORT}/api/v1/health"
  echo "Web UI:   http://localhost:3000"
  echo ""
  echo "Stop: kill \$(cat ${ROOT}/.runtime/install_api.pid) and \$(cat ${ROOT}/.runtime/install_web.pid) or pkill uvicorn / npm run dev"
}

case "$auto_start" in
  none)
    echo "Skipped start (--start none or NEXA_START=none)."
    ;;
  docker)
    start_docker
    ;;
  host)
    start_host
    ;;
  *)
    die "invalid --start / NEXA_START: ${auto_start} (use none|docker|host)"
    ;;
esac

echo ""
echo "Done. Docs: ${ROOT}/docs/SETUP.md"

if [ "${GUIDED_OPEN_DOC:-}" = 1 ] && [ -f "${ROOT}/docs/SETUP.md" ]; then
  if command -v open >/dev/null 2>&1; then
    open "${ROOT}/docs/SETUP.md" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${ROOT}/docs/SETUP.md" 2>/dev/null || true
  fi
fi

#!/bin/bash
# Run the dev job executor on the HOST while Postgres (and often API + bot) run in Docker.
# Codex / DEV_AGENT_COMMAND on macOS are not in the Linux API image.
# Invoked only from host_dev_executor_loop.sh (POSIX sh) so $BASH_ENV is never pre-sourced; see
# that file. Do not `bash` this file directly; use the wrapper or: env -u BASH_ENV -u ENV.

set -euo pipefail

# Re-exec *once* into a clean, non-interactive bash with a terminfo TERM. Never trust the IDE
# (TERM=API is invalid). Pass __OR_HOST_REEXEC__=1 so we do not loop. Clear TERMCAP from the parent.
if [ -z "${__OR_HOST_REEXEC__:-}" ]; then
  _s="${BASH_SOURCE[0]:-$0}"
  if /usr/bin/env -u TERM 2>/dev/null true; then
    exec /usr/bin/env -u BASH_ENV -u ENV -u TERMCAP -u TERM __OR_HOST_REEXEC__=1 SHELL="/bin/bash" TERM="xterm-256color" \
      /bin/bash --noprofile --norc "$_s" "$@"
  else
    exec /usr/bin/env -u BASH_ENV -u ENV TERM="xterm-256color" TERMCAP= __OR_HOST_REEXEC__=1 SHELL="/bin/bash" \
      /bin/bash --noprofile --norc "$_s" "$@"
  fi
fi
unset __OR_HOST_REEXEC__ 2>/dev/null || true

# From here, TERM is set by re-exec; re-assert for the rest of the script
_ensure_terminfo_term() {
  export TERM="xterm-256color"
  unset TERMCAP 2>/dev/null || true
}
_ensure_terminfo_term

ROOT="$(cd "$(dirname "$0")" && cd .. && pwd)"
if [ -z "$ROOT" ] || [ ! -d "$ROOT" ]; then
  echo "error: could not resolve project root" >&2
  exit 1
fi
cd "$ROOT" || exit 1

# Strip TERM / TERMCAP in any .env form. Plain `grep ... ^TERM=` misses `export TERM=API`, which
# then overrides a good parent TERM and breaks tset(1) / reset(1).
if [ -f .env ]; then
  _em="${ROOT}/scripts/emit_sh_exports_from_dotenv.py"
  _py2="${ROOT}/.venv/bin/python3"
  if [ ! -x "$_py2" ]; then
    _py2=$(command -v python3 2>/dev/null || true)
  fi
  if [ -n "$_py2" ] && [ -f "$_em" ]; then
    # python-dotenv parses a whole line as one FOO=bar; bash `source` on raw .env can run reset(1).
    if out=$("$_py2" "$_em" 2>/dev/null) && [ -n "$out" ]; then
      # shellcheck disable=SC1090,SC1091
      eval "$out" || true
    fi
  fi
  _ensure_terminfo_term
fi

: "${DEV_EXECUTOR_ON_HOST:=0}"
if [ "$DEV_EXECUTOR_ON_HOST" != "1" ]; then
  echo "Set DEV_EXECUTOR_ON_HOST=1 in .env (and OPERATOR_AUTO_RUN_DEV_EXECUTOR=false in Docker) before using this script." >&2
  echo "See env.autonomy.example" >&2
  exit 1
fi

PY="${ROOT}/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
  echo "error: need .venv (pip install -r requirements.txt) or python3 on PATH" >&2
  exit 1
fi

DB_PORT="${POSTGRES_HOST_PORT:-5433}"
DB_USER="${POSTGRES_USER:-overwhelm}"
DB_PASS="${POSTGRES_PASSWORD:-overwhelm}"
DB_NAME="${POSTGRES_DB:-overwhelm}"
export DATABASE_URL="postgresql+psycopg2://${DB_USER}:${DB_PASS}@127.0.0.1:${DB_PORT}/${DB_NAME}"

POLL="${OPERATOR_POLL_SECONDS:-20}"
export TERM="xterm-256color"
unset TERMCAP 2>/dev/null || true
echo "host_dev_executor_loop: DATABASE_URL -> 127.0.0.1:${DB_PORT}/${DB_NAME}  poll=${POLL}s  TERM=$TERM" >&2
echo "Using: $PY scripts/dev_agent_executor.py" >&2
if [ "${DEBUG_HOST_EXECUTOR:-0}" = "1" ]; then
  /usr/bin/env -u TERMCAP TERM="xterm-256color" "$PY" -c "import os, sys; print('debug: TERM in python =', repr(os.environ.get('TERM')), file=sys.stderr)"
fi

while true; do
  # No stdin: avoids any tool that reads /dev/tty and blocks on "Terminal type?"
  /usr/bin/env -u TERMCAP TERM="xterm-256color" "$PY" "${ROOT}/scripts/dev_agent_executor.py" </dev/null || true
  sleep "$POLL" || true
done

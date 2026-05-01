#!/bin/sh
# First process is sh(1) — it does not pre-source $BASH_ENV like bash. Then we exec Python,
# which execs bash on the real script; see host_dev_executor_bootstrap.py
D="$(cd "$(dirname "$0")" && pwd)"
# Prefer project venv so imports match; fall back to python3
if [ -x "$D/../.venv/bin/python3" ]; then
  exec "$D/../.venv/bin/python3" "$D/host_dev_executor_bootstrap.py" "$@"
fi
exec /usr/bin/env python3 "$D/host_dev_executor_bootstrap.py" "$@"

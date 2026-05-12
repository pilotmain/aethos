#!/usr/bin/env bash
# Legacy installer — redirects to the one-curl entrypoint (which runs ./scripts/setup.sh).

set -e
cd "$(dirname "$0")/.."
exec bash ./install.sh "$@"

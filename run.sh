#!/usr/bin/env bash
set -e
PORT="${PORT:-8000}"
uvicorn app.main:app --reload --host 0.0.0.0 --port "$PORT"

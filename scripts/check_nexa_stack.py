#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Nexa stack diagnostic (no secrets printed).

Run from repo root:
  python3 scripts/check_nexa_stack.py
  API_BASE_URL=http://127.0.0.1:8000 python3 scripts/check_nexa_stack.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _health(base: str) -> tuple[int, str]:
    url = base.rstrip("/") + "/api/v1/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:  # noqa: S310 — fixed URL
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:
        return -1, str(e)


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    if root not in sys.path:
        sys.path.insert(0, root)

    print("=== Nexa stack check ===\n")

    try:
        from app.core.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        db = (s.database_url or "").lower()
        if "postgres" in db:
            db_kind = "postgresql"
        elif "sqlite" in db:
            db_kind = "sqlite"
        else:
            db_kind = "other"

        token_set = bool((s.nexa_web_api_token or "").strip())
        print("Configuration (from loaded .env / env, secrets redacted):")
        print(f"  DATABASE_URL driver: {db_kind}")
        print(f"  API_BASE_URL: {s.api_base_url}")
        print(f"  NEXA_WEB_ORIGINS: {s.nexa_web_origins}")
        print(f"  NEXA_WEB_API_TOKEN set: {token_set}")
        if token_set:
            print("  → Set the same value as Bearer token on the web login page.")
        purge = getattr(s, "nexa_mission_control_sql_purge", False)
        print(f"  NEXA_MISSION_CONTROL_SQL_PURGE: {purge}")
        print()
    except Exception as exc:
        print(f"Could not import app settings ({exc}).")
        print("  Install deps: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")
        print()

    base = (os.environ.get("API_BASE_URL") or "http://127.0.0.1:8010").strip()
    code, body = _health(base)
    print(f"API GET {base}/api/v1/health → HTTP {code}")
    if code == 200:
        try:
            print(f"  {json.dumps(json.loads(body), indent=2)}")
        except json.JSONDecodeError:
            print(f"  {body[:300]}")
    else:
        print(f"  {body[:400]}")
        print()
        print("Start the API, for example:")
        print("  docker compose up -d")
        print("  ./run_everything.sh start")
        print("  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001")

    print()
    print("Browser / Mission Control checklist:")
    print("  1. Web login → API base must match this API (e.g. http://127.0.0.1:8000).")
    print("  2. User id: web_* / tg_* / … must match the Nexa user that owns rows in the DB.")
    print("  3. If NEXA_WEB_API_TOKEN is set, paste token on login or every mutation returns 401.")
    print("  4. CORS: NEXA_WEB_ORIGINS must include your Next origin (default includes :3000).")
    print("  5. Docker API uses Postgres from compose; local SQLite .env does not apply inside the container.")
    print()


if __name__ == "__main__":
    main()

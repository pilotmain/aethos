#!/usr/bin/env python3
"""
Optional cleanup for unwanted **custom** (LLM profile) agents via REST + SQLite.

Examples::

  export API_BASE=http://127.0.0.1:8000/api/v1
  export X_USER_ID=tg_123456789
  python scripts/cleanup_custom_agents.py --dry-run

Requires ``requests`` (already in project requirements).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="Delete custom agents matching a substring filter.")
    p.add_argument("--api-base", default=os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1"))
    p.add_argument("--user-id", default=os.environ.get("X_USER_ID", "").strip())
    p.add_argument("--contains", default="security_expert", help="Delete handles containing this substring.")
    p.add_argument("--sqlite-path", default=os.path.expanduser(os.environ.get("AETHOS_SQLITE_PATH", "")))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    uid = (args.user_id or "").strip()
    if not uid:
        print("Set --user-id or X_USER_ID.", file=sys.stderr)
        return 2

    try:
        import requests
    except ImportError:
        print("Install requests: pip install requests", file=sys.stderr)
        return 2

    base = args.api_base.rstrip("/")
    needle = (args.contains or "").strip().lower()
    headers = {"X-User-Id": uid}

    r = requests.get(f"{base}/custom-agents", headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"GET /custom-agents failed: {r.status_code} {r.text[:500]}", file=sys.stderr)
        return 1

    payload = r.json()
    agents = payload.get("agents") if isinstance(payload, dict) else None
    if not isinstance(agents, list):
        agents = payload if isinstance(payload, list) else []

    deleted = 0
    for row in agents:
        if not isinstance(row, dict):
            continue
        handle = str(row.get("agent_key") or row.get("handle") or "").strip()
        if not handle or needle not in handle.lower():
            continue
        url = f"{base}/custom-agents/{handle}"
        if args.dry_run:
            print(f"[dry-run] DELETE {url}")
            continue
        dr = requests.delete(url, headers=headers, timeout=30)
        if dr.status_code in (200, 204):
            print(f"Deleted custom agent {handle!r}")
            deleted += 1
        else:
            print(f"DELETE {handle!r} -> {dr.status_code} {dr.text[:300]}", file=sys.stderr)

    db_path = (args.sqlite_path or "").strip()
    if db_path and os.path.isfile(db_path) and not args.dry_run:
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            for table, col in (("user_agents", "agent_key"), ("custom_agents", "handle")):
                try:
                    cur.execute(f"DELETE FROM {table} WHERE {col} LIKE ?", (f"%{needle}%",))
                    if cur.rowcount:
                        print(f"SQLite {table}: removed {cur.rowcount} row(s)")
                except sqlite3.OperationalError:
                    pass
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            print(f"SQLite cleanup skipped: {exc}", file=sys.stderr)

    print(f"Done. API deletions: {deleted}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

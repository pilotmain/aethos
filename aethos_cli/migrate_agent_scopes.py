"""
Phase 61 — optional SQLite migration: normalize ``parent_chat_id`` from bare ``tg_<digits>`` to
``web:tg_<digits>:default``. Usually unnecessary once :func:`~app.services.web_user_id.orchestration_registry_scopes`
includes the bare ``tg_`` scope.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _sqlite_db_path() -> Path | None:
    u = (os.environ.get("DATABASE_URL") or "").strip()
    if not u:
        sys.path.insert(0, str(_repo_root()))
        from app.core.paths import get_default_database_path

        return get_default_database_path()
    low = u.lower()
    if not low.startswith("sqlite"):
        return None
    if "sqlite:///" not in u:
        return None
    raw = u.split("sqlite:///", 1)[1]
    p = Path(raw)
    if p.is_absolute():
        return p
    return (Path.cwd() / p).resolve()


def migrate_agent_scopes(*, apply: bool = False) -> int:
    """List agents with ``tg_%`` scope; optionally rewrite to ``web:tg_*:default``."""
    db_path = _sqlite_db_path()
    if db_path is None:
        print("DATABASE_URL is not SQLite — migration skipped (Phase 61 API scope fix needs no DB rewrite).")
        return 0
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "aethos_orchestration_sub_agents" not in tables:
            print("Table aethos_orchestration_sub_agents missing — nothing to migrate.")
            return 0

        rows = conn.execute(
            "SELECT id, name, parent_chat_id FROM aethos_orchestration_sub_agents "
            "WHERE parent_chat_id LIKE 'tg_%'"
        ).fetchall()
        if not rows:
            print("No agents with parent_chat_id LIKE 'tg_%' — nothing to do.")
            return 0

        print(f"Found {len(rows)} agent row(s) with bare tg_ scope in {db_path}:")
        for rid, name, pch in rows:
            print(f"  {name}: {pch}")

        if not apply:
            print("\nDry-run only. Re-run with --apply to rewrite parent_chat_id to web:tg_*:default.")
            return 0

        conn.execute(
            "UPDATE aethos_orchestration_sub_agents SET parent_chat_id = "
            "'web:' || parent_chat_id || ':default' WHERE parent_chat_id LIKE 'tg_%'"
        )
        conn.commit()

        updated = conn.execute(
            "SELECT name, parent_chat_id FROM aethos_orchestration_sub_agents "
            "WHERE parent_chat_id LIKE '%tg_%'"
        ).fetchall()
        print(f"\nUpdated {len(updated)} row(s); sample:")
        for name, pch in updated[:20]:
            print(f"  {name}: {pch}")
        print("\nRestart the API (and Telegram bot) to reload registry.")
        return 0
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Optional Phase 61 migration: tg_* parent_chat_id → web:tg_*:default (SQLite only)."
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Perform UPDATE (default is dry-run listing only).",
    )
    args = p.parse_args(argv)
    return migrate_agent_scopes(apply=bool(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())

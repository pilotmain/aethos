"""
Add organization_id / team_id columns for Phase 29 multi-tenant RBAC.

Run after upgrading Nexa:

    python migrations/add_rbac_fields.py

Uses :attr:`Settings.nexa_data_dir` for ``mission_control.db`` and ``budget.db``.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.core.config import get_settings


def _try_add_column(conn: sqlite3.Connection, table: str, ddl: str) -> None:
    try:
        conn.execute(ddl)
        print(f"OK: {table}: {ddl.strip()}")
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if "duplicate column" in msg or "already exists" in msg:
            print(f"Skip (exists): {table}")
        else:
            raise


def migrate_mission_control(db_path: Path) -> None:
    if not db_path.is_file():
        print(f"Mission Control DB not found at {db_path}, skipping.")
        return
    with sqlite3.connect(db_path) as conn:
        _try_add_column(
            conn,
            "projects",
            "ALTER TABLE projects ADD COLUMN organization_id TEXT",
        )
        _try_add_column(conn, "projects", "ALTER TABLE projects ADD COLUMN team_id TEXT")
        _try_add_column(conn, "tasks", "ALTER TABLE tasks ADD COLUMN organization_id TEXT")
        _try_add_column(conn, "tasks", "ALTER TABLE tasks ADD COLUMN team_id TEXT")


def migrate_budget(db_path: Path) -> None:
    if not db_path.is_file():
        print(f"Budget DB not found at {db_path}, skipping.")
        return
    with sqlite3.connect(db_path) as conn:
        _try_add_column(
            conn,
            "member_budgets",
            "ALTER TABLE member_budgets ADD COLUMN organization_id TEXT",
        )
        _try_add_column(
            conn,
            "member_budgets",
            "ALTER TABLE member_budgets ADD COLUMN team_id TEXT",
        )


def main() -> int:
    settings = get_settings()
    base = Path(getattr(settings, "nexa_data_dir", None) or "data")
    if not base.is_absolute():
        base = _REPO_ROOT / base
    migrate_mission_control(base / "mission_control.db")
    migrate_budget(base / "budget.db")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

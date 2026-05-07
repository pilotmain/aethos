"""
Phase 62 — write ``~/.aethos/.env`` keys so the Telegram bot uses the same SQLite + orchestration
flags as the API (loaded by :mod:`app.core.config` after the repo ``.env``).
"""

from __future__ import annotations

import sys
from pathlib import Path

from aethos_cli.env_util import upsert_env_file


def configure_bot_env() -> int:
    """Set DATABASE_URL (canonical SQLite) and enable orchestration in ~/.aethos/.env."""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app.core.paths import get_default_sqlite_database_url

    env_file = Path.home() / ".aethos" / ".env"
    upsert_env_file(
        env_file,
        {
            "DATABASE_URL": get_default_sqlite_database_url(),
            "NEXA_AGENT_ORCHESTRATION_ENABLED": "true",
        },
    )
    print(f"Updated {env_file}", flush=True)
    print("  DATABASE_URL → canonical ~/.aethos/data/aethos.db (via get_default_sqlite_database_url)", flush=True)
    print("  NEXA_AGENT_ORCHESTRATION_ENABLED=true", flush=True)
    print("Restart the API and Telegram bot (or `aethos serve`) so processes reload env.", flush=True)
    return 0


__all__ = ["configure_bot_env"]

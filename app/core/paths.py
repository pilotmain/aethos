# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Canonical filesystem paths for AethOS (database location, etc.).

Phase 60: default SQLite lives under ``~/.aethos/data/aethos.db`` so API and Telegram bot
resolve the same file regardless of process cwd. Override with ``DATABASE_URL`` or
``AETHOS_DATA_DIR``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_DB_URL_SCHEME = re.compile(r"^(sqlite(\+[a-z0-9]+)?|postgresql(\+psycopg2)?):", re.I)


def get_aethos_data_dir() -> Path:
    """Durable local data directory (default: ``~/.aethos/data``)."""
    raw = (os.environ.get("AETHOS_DATA_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home() / ".aethos" / "data"


def get_aethos_home_dir() -> Path:
    """
    Operator home for config + runtime parity files (default: ``~/.aethos``).

    ``aethos.json`` and ``workspace/`` live here (not under ``data/``).
    """
    raw = (os.environ.get("AETHOS_HOME_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home() / ".aethos"


def get_runtime_state_path() -> Path:
    """Canonical JSON runtime state (OpenClaw-class persistent runtime parity)."""
    return get_aethos_home_dir() / "aethos.json"


def get_runtime_backups_dir() -> Path:
    """Timestamped ``aethos.*.json`` snapshots (OpenClaw resilience parity)."""
    return get_aethos_home_dir() / "backups"


def get_runtime_corruption_quarantine_dir() -> Path:
    """Invalid / replaced ``aethos.json`` payloads moved aside for inspection."""
    return get_aethos_home_dir() / "corruption_quarantine"


def get_aethos_workspace_root() -> Path:
    """Default workspace root for execution artifacts (``~/.aethos/workspace``)."""
    raw = (os.environ.get("AETHOS_WORKSPACE_HOME") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return get_aethos_home_dir() / "workspace"


def get_default_database_path() -> Path:
    """Canonical SQLite path when using defaults (``…/aethos.db`` under :func:`get_aethos_data_dir`)."""
    return get_aethos_data_dir() / "aethos.db"


def is_valid_sqlalchemy_database_url(url: str) -> bool:
    """True when ``url`` is a single-line SQLAlchemy database URL (not docs or examples)."""
    v = (url or "").strip()
    if not v or len(v) > 512:
        return False
    if any(c in v for c in ("\n", "\r", "#")):
        return False
    return bool(_DB_URL_SCHEME.match(v))


def get_default_sqlite_database_url() -> str:
    """
    Default ``DATABASE_URL`` for SQLite — absolute path so API and bot agree without cwd.

    Format matches SQLAlchemy ``sqlite:///`` + absolute path (four slashes after ``sqlite:`` on Unix).
    """
    p = get_default_database_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{p.resolve().as_posix()}"


__all__ = [
    "get_aethos_data_dir",
    "get_aethos_home_dir",
    "get_aethos_workspace_root",
    "get_default_database_path",
    "get_default_sqlite_database_url",
    "get_runtime_backups_dir",
    "get_runtime_corruption_quarantine_dir",
    "get_runtime_state_path",
    "is_valid_sqlalchemy_database_url",
]

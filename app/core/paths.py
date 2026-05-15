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
    "get_default_database_path",
    "get_default_sqlite_database_url",
    "is_valid_sqlalchemy_database_url",
]

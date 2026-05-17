# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Calm database lock handling during setup."""

from __future__ import annotations

import re
from typing import Any


def is_database_locked_error(message: str) -> bool:
    low = (message or "").lower()
    return "database is locked" in low or "sqlite3.operationalerror" in low and "locked" in low


def build_db_lock_guidance(*, active_runtime: bool = True) -> dict[str, Any]:
    return {
        "setup_db_lock_guidance": {
            "title": "AethOS detected an active runtime using the database.",
            "options": [
                "Use the existing runtime",
                "Stop and restart the runtime",
                "Retry database initialization",
                "Continue and validate later",
            ],
            "commands": {
                "use_existing": "aethos doctor",
                "restart_runtime": "aethos restart runtime",
                "retry_db": "aethos init-db",
                "validate_later": "aethos setup validate",
            },
            "active_runtime": active_runtime,
            "no_traceback": True,
            "bounded": True,
        }
    }


def format_calm_db_lock_message(stderr: str) -> str:
    if not is_database_locked_error(stderr):
        return ""
    return (
        "AethOS detected an active runtime using the database.\n"
        "You can:\n"
        "  1. Use the existing runtime\n"
        "  2. Stop and restart the runtime  (aethos restart runtime)\n"
        "  3. Retry database initialization  (aethos init-db)\n"
        "  4. Continue and validate later  (aethos setup validate)\n"
    )


def sanitize_setup_error(stderr: str, *, max_len: int = 400) -> str:
    if is_database_locked_error(stderr):
        return format_calm_db_lock_message(stderr)
    text = stderr or ""
    if "traceback" in text.lower():
        for line in reversed(text.splitlines()):
            s = line.strip()
            if s and not s.lower().startswith("file ") and "traceback" not in s.lower():
                text = s
                break
        else:
            text = "Database initialization needs attention"
    line = re.sub(r"\s+", " ", text.strip())
    if len(line) > max_len:
        line = line[: max_len - 3] + "..."
    return line or "Database initialization needs attention — run: aethos setup validate"

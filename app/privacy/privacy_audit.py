# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Append-only JSON audit lines under ``~/.aethos/logs`` (no raw secret payloads)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def privacy_logs_dir() -> Path:
    return Path.home() / ".aethos" / "logs"


def append_privacy_line(rel_name: str, record: dict[str, Any]) -> None:
    """Write one JSON line to ``~/.aethos/logs/<rel_name>`` (creates parents)."""
    from app.core.config import get_settings

    s = get_settings()
    if not bool(getattr(s, "aethos_privacy_audit_enabled", True)):
        return
    path = privacy_logs_dir() / rel_name
    payload = {"ts": time.time(), **record}
    line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.open("a", encoding="utf-8").write(line)

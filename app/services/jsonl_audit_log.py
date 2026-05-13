# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Append-only JSONL audit log on disk (enterprise complement to DB ``audit_logs``)."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings

_log = logging.getLogger(__name__)
_lock = threading.Lock()


def log_jsonl_audit_event(
    *,
    user_id: str,
    action: str,
    outcome: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Append one JSON object to today's file under ``AUDIT_DIR`` when ``AUDIT_ENABLED``."""
    s = get_settings()
    if not bool(getattr(s, "audit_enabled", True)):
        return
    raw_dir = (getattr(s, "audit_dir", None) or "").strip()
    base = Path(raw_dir or str(Path.home() / ".aethos" / "audit")).expanduser()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log.warning("audit jsonl mkdir failed: %s", exc)
        return

    now = datetime.now(timezone.utc)
    entry = {
        "timestamp": now.isoformat(),
        "user_id": (user_id or "")[:256],
        "action": (action or "")[:128],
        "outcome": (outcome or "")[:64],
        "details": details or {},
    }
    day = now.strftime("%Y-%m-%d")
    path = base / f"{day}.jsonl"
    line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
    with _lock:
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError as exc:
            _log.warning("audit jsonl write failed: %s", exc)


__all__ = ["log_jsonl_audit_event"]

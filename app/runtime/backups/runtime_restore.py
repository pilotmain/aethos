# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Restore ``aethos.json`` from a verified backup file."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.runtime.runtime_state import save_runtime_state

_LOG = logging.getLogger("aethos.runtime.restore")


def restore_runtime_state_from_file(backup_path: Path) -> dict[str, Any]:
    """Load JSON object from ``backup_path`` and atomically replace runtime state."""
    raw = backup_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("backup root must be a JSON object")
    save_runtime_state(data)
    _LOG.info("runtime.restored_from_backup path=%s", backup_path)
    return {"ok": True, "path": str(backup_path)}

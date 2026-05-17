# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Uvicorn reload parent vs worker detection (Phase 4 Step 19)."""

from __future__ import annotations

import os
import sys
from typing import Any


def detect_uvicorn_process_kind() -> str:
    """Return ``reloader_parent``, ``api_worker``, or ``other``."""
    argv = " ".join(sys.argv)
    if "app.main:app" not in argv and "uvicorn" not in argv:
        return "other"
    if os.environ.get("AETHOS_UVICORN_WORKER", "").lower() in ("1", "true", "yes"):
        return "api_worker"
    if "--reload" in argv:
        return "reloader_parent"
    return "api_worker"


def mark_uvicorn_worker() -> None:
    os.environ["AETHOS_UVICORN_WORKER"] = "1"


def filter_api_process_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop uvicorn reload parent when a child worker is also present."""
    api_rows = [r for r in rows if "app.main:app" in (r.get("command") or "")]
    if len(api_rows) <= 1:
        return api_rows
    reloaders = [r for r in api_rows if "--reload" in (r.get("command") or "")]
    workers = [r for r in api_rows if r not in reloaders]
    if workers and reloaders:
        return workers
    return api_rows

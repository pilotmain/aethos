# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Shared paths for Cursor/dev handoff marker files (payload, cursor_task_path, or default .agent_tasks)."""
from __future__ import annotations

from pathlib import Path

# app/services/ -> app/ -> project
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_TASKS_DIR = PROJECT_ROOT / ".agent_tasks"


def resolve_handoff_marker_path(job) -> Path | None:
    p = str((job.payload_json or {}).get("handoff_marker_path") or "").strip()
    if p:
        return Path(p)
    ctp = str(getattr(job, "cursor_task_path", None) or "").strip()
    if ctp:
        pa = Path(ctp)
        if pa.suffix.lower() == ".md":
            return pa.parent / f"{pa.stem}.done.md"
    if (getattr(job, "worker_type", None) or "") == "dev_executor" and getattr(job, "id", None) is not None:
        return AGENT_TASKS_DIR / f"dev_job_{job.id}.done.md"
    return None

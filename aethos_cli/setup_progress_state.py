# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Setup progress persistence (Phase 4 Step 17)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROGRESS_FILE = Path.home() / ".aethos" / "setup" / "setup_progress.json"

SECTIONS = (
    "welcome",
    "runtime_strategy",
    "providers",
    "mission_control",
    "workspace",
    "operator_onboarding",
    "readiness",
    "launch",
)


def load_setup_progress() -> dict[str, Any]:
    if not PROGRESS_FILE.is_file():
        return _empty()
    try:
        blob = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        return blob if isinstance(blob, dict) else _empty()
    except (OSError, json.JSONDecodeError):
        return _empty()


def save_setup_progress(**updates: Any) -> None:
    blob = load_setup_progress()
    for k, v in updates.items():
        if k in ("completed_sections", "skipped_sections", "failed_sections") and isinstance(v, list):
            existing = list(blob.get(k) or [])
            for item in v:
                if item not in existing:
                    existing.append(item)
            blob[k] = existing
        else:
            blob[k] = v
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(blob, indent=2), encoding="utf-8")


def mark_section(section: str, *, completed: bool = True, failed: bool = False, skipped: bool = False) -> None:
    if completed:
        save_setup_progress(current_section=section, completed_sections=[section])
    if skipped:
        save_setup_progress(skipped_sections=[section])
    if failed:
        save_setup_progress(failed_sections=[section], last_failed_section=section)


def build_progress_status() -> dict[str, Any]:
    p = load_setup_progress()
    completed = list(p.get("completed_sections") or [])
    skipped = list(p.get("skipped_sections") or [])
    failed = list(p.get("failed_sections") or [])
    pending = [s for s in SECTIONS if s not in completed and s not in skipped]
    return {
        "current_section": p.get("current_section"),
        "completed_sections": completed,
        "skipped_sections": skipped,
        "failed_sections": failed,
        "pending_sections": pending,
        "last_prompt": p.get("last_prompt"),
        "runtime_strategy": p.get("runtime_strategy"),
        "mission_control_seeded": p.get("mission_control_seeded"),
        "onboarding_profile": p.get("onboarding_profile"),
        "repair_recommendations": p.get("repair_recommendations") or [],
        "phase": "phase4_step17",
    }


def _empty() -> dict[str, Any]:
    return {
        "completed_sections": [],
        "skipped_sections": [],
        "failed_sections": [],
        "pending_sections": list(SECTIONS),
    }

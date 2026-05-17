# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Setup continuity — resume, pause, and recovery state (Phase 4 Step 15)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SETUP_STATE = Path.home() / ".aethos" / ".setup_state.json"
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


def _load_state() -> dict[str, Any] | None:
    if not SETUP_STATE.is_file():
        return None
    try:
        return json.loads(SETUP_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_setup_continuity(*, repo_root: Path | None = None) -> dict[str, Any]:
    state = _load_state()
    step = int(state.get("step", 0)) if state else 0
    data = (state or {}).get("data") if isinstance(state, dict) else {}
    completed = _sections_for_step(step)
    return {
        "setup_continuity": {
            "resumable": state is not None and step > 0,
            "current_step": step,
            "completed_sections": completed,
            "pending_sections": [s for s in SECTIONS if s not in completed],
            "global_commands": ["help", "back", "skip", "status", "resume", "retry", "exit"],
            "welcome_back_message": (
                "Welcome back. Continue where you left off, review your configuration, or restart onboarding."
                if state
                else "No saved setup — run `aethos setup` to begin."
            ),
            "persistence": {
                "setup_state": SETUP_STATE.is_file(),
                "onboarding_profile": (Path.home() / ".aethos" / "onboarding_profile.json").is_file(),
                "env_configured": bool(data.get("updates")) if isinstance(data, dict) else False,
            },
            "phase": "phase4_step20",
            "bounded": True,
        }
    }


def _sections_for_step(step: int) -> list[str]:
    if step >= 4:
        return list(SECTIONS)
    if step >= 3:
        return list(SECTIONS[:6])
    if step >= 2:
        return list(SECTIONS[:4])
    if step >= 1:
        return list(SECTIONS[:2])
    return []

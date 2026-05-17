# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Defer relationship onboarding until first operational interaction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_STATE_PATH = Path.home() / ".aethos" / "first_run_onboarding.json"
_PROFILE_PATH = Path.home() / ".aethos" / "onboarding_profile.json"


def _read_state() -> dict[str, Any]:
    if not _STATE_PATH.is_file():
        return {}
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(blob: dict[str, Any]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(blob, indent=2), encoding="utf-8")


def _load_profile() -> dict[str, Any]:
    if not _PROFILE_PATH.is_file():
        return {}
    try:
        blob = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
        return blob.get("profile") if isinstance(blob, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def mark_onboarding_deferred_from_setup() -> None:
    """Installer finished — relationship onboarding waits for first launch."""
    state = _read_state()
    state.update({"deferred_from_setup": True, "completed": False, "pending_first_launch": True})
    _write_state(state)


def mark_first_run_onboarding_complete() -> None:
    state = _read_state()
    state.update({"completed": True, "pending_first_launch": False})
    _write_state(state)


def needs_first_run_operator_onboarding() -> bool:
    profile = _load_profile()
    if profile.get("orchestrator_intro_complete") or profile.get("display_name"):
        return False
    state = _read_state()
    return bool(state.get("pending_first_launch")) or bool(state.get("deferred_from_setup"))


def build_first_run_onboarding_prompt() -> dict[str, Any]:
    pending = needs_first_run_operator_onboarding()
    return {
        "first_run_operator_onboarding": {
            "pending": pending,
            "welcome": (
                "Welcome — I'm AethOS.\n\n"
                "I coordinate runtime workers, providers, governance, and operational systems.\n\n"
                "Before we begin, I'd like to understand how you work so I can adapt intelligently over time."
                if pending
                else ""
            ),
            "questions": [
                {"id": "display_name", "label": "What should I call you?", "optional": True},
                {"id": "tone", "label": "Preferred tone", "optional": True},
                {"id": "goals", "label": "Main goals with AethOS", "optional": True},
                {"id": "profession", "label": "What do you do professionally?", "optional": True},
                {"id": "working_style", "label": "Preferred working style", "optional": True},
            ],
            "surface": "mission_control_first_launch",
            "installer_skips_relationship_onboarding": True,
            "bounded": True,
        }
    }


__all__ = [
    "build_first_run_onboarding_prompt",
    "mark_first_run_onboarding_complete",
    "mark_onboarding_deferred_from_setup",
    "needs_first_run_operator_onboarding",
]

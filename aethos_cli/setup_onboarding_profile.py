# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""First-run personal onboarding profile (Phase 4 Step 4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aethos_cli.ui import get_input, print_info, print_success


def onboarding_profile_path() -> Path:
    return Path.home() / ".aethos" / "onboarding_profile.json"


def run_onboarding_profile_questions() -> dict[str, Any]:
    """Collect operator preferences — bounded, optional skips."""
    print_info("Personal onboarding (optional — Enter skips any question).")
    profile: dict[str, Any] = {
        "display_name": (get_input("What should AethOS call you?") or "").strip() or None,
        "assistant_name": (get_input("What would you like to call AethOS?") or "AethOS").strip(),
        "professional_context": (get_input("What do you do professionally?") or "").strip() or None,
        "main_goals": (get_input("Main goals with AethOS?") or "").strip() or None,
        "work_types": (get_input("Kinds of work AethOS should help with?") or "").strip() or None,
        "tone": (get_input("Preferred tone (concise/friendly/formal/technical/proactive)", "concise") or "concise").strip(),
        "privacy_preference": (
            get_input("Privacy preference (local-first/balanced/cloud-ok)", "balanced") or "balanced"
        ).strip(),
        "cost_preference": (
            get_input("Cost preference (lowest-cost/best-quality/balanced)", "balanced") or "balanced"
        ).strip(),
    }
    return {k: v for k, v in profile.items() if v is not None}


def save_onboarding_profile(profile: dict[str, Any]) -> Path:
    path = onboarding_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"v": 1, "profile": profile}, indent=2), encoding="utf-8")
    print_success(f"Onboarding profile saved → {path}")
    return path


def load_onboarding_profile() -> dict[str, Any] | None:
    path = onboarding_profile_path()
    if not path.is_file():
        return None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        return blob.get("profile") if isinstance(blob, dict) else None
    except (OSError, json.JSONDecodeError):
        return None

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Setup operator profile API surface (Phase 4 Step 15)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_profile() -> dict[str, Any]:
    path = Path.home() / ".aethos" / "onboarding_profile.json"
    if not path.is_file():
        return {}
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        return blob.get("profile") if isinstance(blob, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def build_setup_operator_profile() -> dict[str, Any]:
    profile = _load_profile()
    return {
        "setup_operator_profile": {
            "present": bool(profile),
            "display_name": profile.get("display_name"),
            "tone": profile.get("tone"),
            "profession": profile.get("profession") or profile.get("professional_context"),
            "goals": profile.get("goals") or profile.get("main_goals"),
            "privacy_preference": profile.get("privacy_preference"),
            "coding_preference": profile.get("coding_preference"),
            "operational_preference": profile.get("operational_preference"),
            "orchestrator_intro_complete": profile.get("orchestrator_intro_complete"),
            "optional_fields_skippable": True,
            "memory_purpose": "Improve operational usefulness without invasive collection",
            "bounded": True,
        },
        "profile": profile,
    }

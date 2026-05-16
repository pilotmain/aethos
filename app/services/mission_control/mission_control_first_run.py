# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control first-run guided experience (Phase 4 Step 10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _profile() -> dict[str, Any]:
    path = Path.home() / ".aethos" / "onboarding_profile.json"
    if not path.is_file():
        return {}
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        return blob.get("profile") if isinstance(blob, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def build_mission_control_first_run(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    profile = _profile()
    setup_complete = Path.home() / ".aethos" / "onboarding_profile.json"
    return {
        "mission_control_first_run": {
            "welcome": _welcome_message(profile),
            "steps": [
                {"id": "runtime_overview", "title": "Runtime overview", "path": "/mission-control/runtime-overview"},
                {"id": "providers", "title": "Provider setup", "path": "/mission-control/providers"},
                {"id": "workspace", "title": "Workspace", "path": "/mission-control/workspace-intelligence"},
                {"id": "plugins", "title": "Plugins", "path": "/mission-control/plugins"},
                {"id": "privacy", "title": "Privacy posture", "path": "/mission-control/privacy"},
                {"id": "readiness", "title": "Operational readiness", "path": "/mission-control/executive-overview"},
            ],
            "personalized": bool(profile),
            "display_name": profile.get("display_name"),
            "first_run_complete": setup_complete.is_file() and bool(truth.get("runtime_readiness_score")),
            "tone": "premium_calm",
            "bounded": True,
        },
        "operational_readiness_summary": {
            "production_ready": (truth.get("production_runtime_posture") or {}).get("ready"),
            "readiness_score": truth.get("runtime_readiness_score"),
            "calm": (truth.get("calmness_integrity") or {}).get("calm") if isinstance(truth.get("calmness_integrity"), dict) else None,
        },
    }


def _welcome_message(profile: dict[str, Any]) -> str:
    name = profile.get("display_name") or profile.get("user_address")
    if name:
        return f"Welcome to AethOS, {name}. Your orchestrator is ready — calm, explainable, enterprise-grade."
    return "Welcome to AethOS. Your orchestrator coordinates workers, providers, and governance from one place."

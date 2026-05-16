# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control first-impression bundle (Phase 4 Step 15)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.mission_control.mission_control_first_run import build_mission_control_first_run
from app.services.setup.mission_control_ready_state import build_mission_control_ready_state
from app.services.setup.setup_operator_profile_api import build_setup_operator_profile
from app.services.setup.setup_status import build_setup_status


def build_setup_first_impression(*, repo_root: Path | None = None, truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    status = build_setup_status(repo_root=repo_root)
    mc_ready = build_mission_control_ready_state(repo_root=repo_root)
    profile = build_setup_operator_profile()
    first_run = build_mission_control_first_run(truth)
    name = profile.get("setup_operator_profile", {}).get("display_name")
    greeting = f"Welcome to AethOS{', ' + name if name else ''}."
    return {
        "setup_first_impression": {
            "greeting": greeting,
            "headline": "Your orchestrator is ready — Mission Control is connected.",
            "setup_complete": status.get("complete"),
            "mission_control_ready": mc_ready.get("ready"),
            "recommended_next_steps": [
                "Open The Office — operational command center",
                "Review provider routing",
                "Explore governance timeline",
            ],
            "auto_seeded": {
                "api_connection": mc_ready.get("ready"),
                "onboarding_state": profile.get("setup_operator_profile", {}).get("present"),
            },
            "no_manual_token_required": mc_ready.get("ready"),
            "tone": "premium_calm",
            "bounded": True,
        },
        "mission_control_first_run": first_run.get("mission_control_first_run"),
        "operational_readiness_summary": first_run.get("operational_readiness_summary"),
        "setup_status": status,
    }

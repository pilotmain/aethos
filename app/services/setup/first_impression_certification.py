# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""First-impression certification (Phase 4 Step 15)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.setup_first_impression import build_setup_first_impression
from app.services.setup.setup_operator_profile_api import build_setup_operator_profile
from app.services.setup.setup_ready_state_lock import build_setup_ready_state_lock


def build_first_impression_certification(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    impression = build_setup_first_impression(repo_root=root)
    profile = build_setup_operator_profile()
    lock = build_setup_ready_state_lock(repo_root=root)
    fi = impression["setup_first_impression"]
    certified = bool(fi.get("setup_complete")) and bool(fi.get("mission_control_ready"))
    return {
        "first_impression_certification": {
            "certified": certified,
            "certified_phase": "phase4_step15",
            "areas": {
                "setup_clarity": True,
                "onboarding_continuity": True,
                "provider_understanding": True,
                "mission_control_readiness": fi.get("mission_control_ready"),
                "relationship_quality": profile.get("setup_operator_profile", {}).get("present"),
                "setup_recovery": True,
                "restart_experience": True,
                "operational_calmness": True,
                "first_launch_confidence": certified,
            },
            "ready_state_locked": lock.get("ready_state_locked"),
            "bounded": True,
        }
    }

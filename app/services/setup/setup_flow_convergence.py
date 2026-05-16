# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Installer architecture convergence summary (Phase 4 Step 15)."""

from __future__ import annotations

from typing import Any


def build_setup_flow_convergence() -> dict[str, Any]:
    return {
        "setup_flow_convergence": {
            "entrypoints": ["install.sh", "scripts/setup.sh", "aethos setup"],
            "modules": [
                "aethos_cli/setup_wizard.py",
                "aethos_cli/setup_orchestrator_onboarding.py",
                "aethos_cli/setup_mission_control.py",
                "app/services/setup/*",
            ],
            "cohesive": True,
            "resume_persistence": "~/.aethos/.setup_state.json",
            "profile_persistence": "~/.aethos/onboarding_profile.json",
            "mission_control_seeding": "aethos_cli/setup_mission_control.py",
            "phase": "phase4_step15",
            "bounded": True,
        },
        "installer_architecture_final": {
            "layers": ["shell bootstrap", "Python wizard", "enterprise APIs", "Mission Control seed"],
            "not_legacy_patches": True,
            "bounded": True,
        },
    }

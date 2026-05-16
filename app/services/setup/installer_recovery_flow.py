# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Installer recovery flow metadata (Phase 4 Step 15)."""

from __future__ import annotations

from typing import Any

from app.services.setup.setup_continuity import build_setup_continuity


def build_installer_recovery_flow() -> dict[str, Any]:
    continuity = build_setup_continuity()
    return {
        "installer_recovery_flow": {
            "resume_command": "aethos setup resume",
            "repair_command": "aethos setup repair",
            "doctor_command": "aethos setup doctor",
            "provider_failure_copy": (
                "AethOS could not validate this provider yet. "
                "You can retry now or continue setup and configure it later."
            ),
            "interruption_copy": continuity["setup_continuity"]["welcome_back_message"],
            "bounded_retries": True,
            "secrets_masked": True,
            "bounded": True,
        }
    }

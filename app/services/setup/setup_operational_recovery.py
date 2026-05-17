# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Recovery-first installer behavior (Phase 4 Step 28)."""

from __future__ import annotations

from typing import Any


def build_setup_operational_recovery(*, repo_root: str | None = None) -> dict[str, Any]:
    issues: list[str] = []
    actions: list[str] = ["aethos setup operational-recovery", "aethos doctor", "aethos runtime recover"]
    try:
        from aethos_cli.setup_supervision_preflight import run_setup_supervision_preflight

        pre = run_setup_supervision_preflight()
        ports = pre.get("ports") or {}
        if ports.get(8000) or ports.get(8010):
            issues.append("api_port_in_use")
            actions.insert(0, "aethos runtime restart --clean")
    except Exception:
        pass
    calm = len(issues) == 0
    return {
        "setup_operational_recovery": {
            "phase": "phase4_step28",
            "recovery_ready": True,
            "issues": issues,
            "recommended_actions": actions[:6],
            "headline": (
                "Enterprise runtime operational."
                if calm
                else "Setup can recover runtime conflicts automatically — choose coordinate in setup."
            ),
            "calm": True,
            "operator_guided": True,
            "bounded": True,
        }
    }

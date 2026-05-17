# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Recovery-first installer behavior (Phase 4 Step 28)."""

from __future__ import annotations

from typing import Any


def build_setup_operational_recovery(*, repo_root: str | None = None) -> dict[str, Any]:
    issues: list[str] = []
    actions: list[str] = [
        "aethos start",
        "aethos runtime recover",
        "aethos doctor",
        "aethos setup repair",
    ]
    repair_scope = [
        "runtime ownership conflicts",
        "stale startup locks",
        "broken Mission Control startup",
        "database coordination issues",
        "partial hydration states",
        "stale Telegram pollers",
    ]
    try:
        from app.services.runtime.runtime_health_authority import build_canonical_runtime_health

        ha = build_canonical_runtime_health()["runtime_health_authority"]
        if ha.get("stale_session"):
            issues.append("stale_runtime_session")
            actions.insert(0, "aethos start")
        if not ha.get("mission_control_reachable") and ha.get("api_reachable"):
            issues.append("mission_control_unreachable")
        if not ha.get("ownership_valid"):
            issues.append("ownership_conflict")
    except Exception:
        pass
    try:
        from aethos_cli.setup_supervision_preflight import run_setup_supervision_preflight

        pre = run_setup_supervision_preflight()
        ports = pre.get("ports") or {}
        canonical = pre.get("canonical_ports") or {}
        api_port = canonical.get("api", 8010)
        if ports.get(api_port) and "stale_runtime_session" not in issues:
            issues.append("api_port_in_use")
    except Exception:
        pass
    calm = len(issues) == 0
    return {
        "setup_operational_recovery": {
            "phase": "phase4_step30",
            "recovery_ready": True,
            "issues": issues,
            "repair_scope": repair_scope,
            "recommended_actions": actions[:6],
            "headline": (
                "AethOS is operational."
                if calm
                else "AethOS detected an incomplete or stale runtime session."
            ),
            "calm": True,
            "operator_guided": True,
            "bounded": True,
        }
    }

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime supervision checks before setup DB/schema work."""

from __future__ import annotations

import os
from typing import Any

from aethos_cli.ui import print_box, print_info, select


def run_setup_supervision_preflight() -> dict[str, Any]:
    from app.services.runtime.runtime_health_authority import build_canonical_runtime_health
    from app.services.runtime.runtime_port_coordination import get_canonical_runtime_ports, probe_runtime_ports

    health = build_canonical_runtime_health()
    ha = health["runtime_health_authority"]
    ports = probe_runtime_ports()
    canonical = get_canonical_runtime_ports()
    ownership: dict[str, Any] = {}
    try:
        from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status

        ownership = build_runtime_ownership_status().get("runtime_ownership") or {}
    except Exception:
        ownership = {}
    stale = bool(ha.get("stale_session"))
    operational = bool(ha.get("operational"))
    conflicts = list(ha.get("ownership_conflicts") or [])
    needs_recovery = stale or (bool(conflicts) and not operational)
    return {
        "ports": ports,
        "canonical_ports": canonical,
        "ownership": ownership,
        "health": health,
        "operational": operational,
        "stale_session": stale,
        "ownership_conflicts": conflicts,
        "any_conflict": needs_recovery,
        "needs_recovery": needs_recovery,
    }


def coordinate_runtime_for_setup(*, auto: bool = False) -> dict[str, Any]:
    """Stop conflicting runtimes, release locks, and repair coordination."""
    from app.services.runtime.runtime_port_coordination import coordinate_runtime_ports

    return coordinate_runtime_ports(auto=auto, restart=False)


def prompt_setup_supervision_if_needed() -> None:
    pre = run_setup_supervision_preflight()
    if pre.get("operational"):
        return
    if not pre.get("needs_recovery"):
        return

    if os.environ.get("NEXA_NONINTERACTIVE") == "1":
        print_info("AethOS detected an older runtime session. Coordinating recovery…")
        result = coordinate_runtime_for_setup(auto=True)
        print_info(result.get("message") or "Runtime coordination recovered.")
        return

    ports = pre.get("ports") or {}
    canonical = pre.get("canonical_ports") or {}
    lines = [
        "AethOS detected an older runtime session.",
        "Coordinating recovery…",
        "",
        f"API port {canonical.get('api', 8010)}: {'in use' if ports.get(canonical.get('api', 8010)) else 'free'}",
        f"Legacy worker 8000: {'in use' if ports.get(8000) else 'free'}",
        f"Mission Control 3000: {'in use' if ports.get(3000) else 'free'}",
        "",
        "AethOS can repair:",
        "• runtime ownership conflicts",
        "• stale startup locks",
        "• broken Mission Control startup",
        "• database coordination issues",
        "• partial hydration states",
        "• stale Telegram pollers",
    ]
    own = pre.get("ownership") or {}
    if own.get("holder_pid"):
        lines.append(f"Runtime ownership: held by PID {own.get('holder_pid')}")
    print_box("Runtime supervision", lines)
    choice = select(
        "Proceed with coordinated recovery?",
        [
            ("Coordinate automatically (recommended)", "coordinate", "Stop stale processes and release locks"),
            ("Continue using current runtime", "use", "Skip process coordination"),
            ("Advanced clean recovery", "advanced", "Force clean stop without auto-restart"),
        ],
        default_index=0,
    )
    if choice in ("coordinate", "advanced"):
        result = coordinate_runtime_for_setup(auto=True)
        print_info(result.get("message") or "Operational runtime conflict recovered — continuing setup.")
    else:
        print_info("Proceeding without coordination — stale processes may block startup.")
    print_info("Proceeding with enterprise setup.")

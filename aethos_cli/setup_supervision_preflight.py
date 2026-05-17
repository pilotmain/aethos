# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime supervision checks before setup DB/schema work."""

from __future__ import annotations

import socket
from typing import Any

from aethos_cli.ui import print_box, print_info, select


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def run_setup_supervision_preflight() -> dict[str, Any]:
    ports = {8000: _port_open(8000), 8010: _port_open(8010), 3000: _port_open(3000)}
    ownership: dict[str, Any] = {}
    try:
        from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status

        ownership = build_runtime_ownership_status().get("runtime_ownership") or {}
    except Exception:
        ownership = {}
    held = bool(ownership.get("holder_pid"))
    return {"ports": ports, "ownership": ownership, "any_conflict": any(ports.values()) or held}


def coordinate_runtime_for_setup(*, auto: bool = False) -> dict[str, Any]:
    """Stop conflicting runtimes and repair DB coordination when installer requests takeover."""
    try:
        from app.services.runtime.runtime_recovery_authority import execute_runtime_recovery

        return execute_runtime_recovery(clean=auto, restart=False)
    except Exception as exc:
        return {"ok": False, "message": str(exc)[:160]}


def prompt_setup_supervision_if_needed() -> None:
    pre = run_setup_supervision_preflight()
    if not pre.get("any_conflict"):
        return
    ports = pre.get("ports") or {}
    lines = [
        "AethOS detected an active runtime session.",
        "",
        f"API port 8000: {'in use' if ports.get(8000) else 'free'}",
        f"API port 8010: {'in use' if ports.get(8010) else 'free'}",
        f"Mission Control 3000: {'in use' if ports.get(3000) else 'free'}",
        "",
        "Recommended action:",
        "• Safely coordinate and restart the runtime",
    ]
    own = pre.get("ownership") or {}
    if own.get("holder_pid"):
        lines.append(f"Runtime ownership: held by PID {own.get('holder_pid')}")
    print_box("Runtime supervision", lines)
    choice = select(
        "How should setup proceed?",
        [
            ("Coordinate automatically (recommended)", "coordinate", "Stop conflicts and repair DB locks"),
            ("Continue using current runtime", "use", "Skip process coordination"),
            ("Enter advanced recovery mode", "advanced", "Full clean stop without auto-restart"),
        ],
        default_index=0,
    )
    if choice == "coordinate":
        result = coordinate_runtime_for_setup(auto=True)
        print_info(result.get("message") or "Enterprise runtime coordination recovered successfully.")
    elif choice == "advanced":
        result = coordinate_runtime_for_setup(auto=True)
        print_info(result.get("message") or "Advanced recovery complete — validate with `aethos doctor`.")
    else:
        print_info("Proceeding with existing runtime — duplicate processes may require `aethos runtime recover`.")
    print_info("Proceeding with enterprise setup.")

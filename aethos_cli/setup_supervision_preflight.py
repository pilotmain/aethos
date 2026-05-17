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
    return {"ports": ports, "ownership": ownership, "any_conflict": any(ports.values()) or bool(ownership.get("held"))}


def prompt_setup_supervision_if_needed() -> None:
    pre = run_setup_supervision_preflight()
    if not pre.get("any_conflict"):
        return
    ports = pre.get("ports") or {}
    lines = [
        f"API port 8000: {'in use' if ports.get(8000) else 'free'}",
        f"API port 8010: {'in use' if ports.get(8010) else 'free'}",
        f"Mission Control 3000: {'in use' if ports.get(3000) else 'free'}",
    ]
    own = pre.get("ownership") or {}
    if own.get("held"):
        lines.append(f"Runtime ownership: held by {own.get('owner_pid') or 'another process'}")
    print_box("Runtime supervision", lines + ["Setup can continue — choose how to proceed."])
    select(
        "How should setup proceed?",
        [
            ("Use existing runtime", "use", "Skip starting duplicate API processes"),
            ("Restart runtime after setup", "restart", "Run aethos restart runtime when done"),
            ("Continue setup only", "continue", "Configure files; validate later"),
        ],
        default_index=0,
    )
    print_info("Proceeding with enterprise setup.")

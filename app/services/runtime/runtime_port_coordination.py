# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Canonical runtime port coordination — automatic stale session recovery."""

from __future__ import annotations

import os
import socket
from typing import Any


def get_canonical_runtime_ports() -> dict[str, int]:
    api = int(os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010")
    return {"legacy_worker": 8000, "api": api, "mission_control": 3000}


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def probe_runtime_ports() -> dict[int, bool]:
    ports = get_canonical_runtime_ports()
    return {ports["legacy_worker"]: _port_open(ports["legacy_worker"]), ports["api"]: _port_open(ports["api"]), ports["mission_control"]: _port_open(ports["mission_control"])}


def coordinate_runtime_ports(*, auto: bool = True, restart: bool = False) -> dict[str, Any]:
    """Stop stale processes, release locks, optionally restart process groups."""
    from app.services.runtime.runtime_recovery_authority import execute_runtime_recovery

    return execute_runtime_recovery(clean=auto, restart=restart)


def build_runtime_port_coordination(*, health: dict[str, Any] | None = None) -> dict[str, Any]:
    health = health or {}
    ha = health.get("runtime_health_authority") or {}
    ports = probe_runtime_ports()
    open_ports = [p for p, open_ in ports.items() if open_]
    stale = bool(ha.get("stale_session"))
    operational = bool(ha.get("operational"))
    return {
        "runtime_port_coordination": {
            "ports": ports,
            "open_ports": open_ports,
            "stale_session": stale,
            "operational": operational,
            "needs_recovery": stale or (bool(open_ports) and not operational),
            "auto_coordinate_recommended": stale or (bool(open_ports) and not operational),
            "bounded": True,
        }
    }


__all__ = [
    "build_runtime_port_coordination",
    "coordinate_runtime_ports",
    "get_canonical_runtime_ports",
    "probe_runtime_ports",
]

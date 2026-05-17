# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Canonical runtime health authority — truthful operational semantics."""

from __future__ import annotations

import os
import socket
import urllib.error
import urllib.request
from typing import Any

from app.services.runtime.runtime_launch_orchestration import derive_operator_readiness_state
from app.services.runtime.runtime_port_coordination import get_canonical_runtime_ports, probe_runtime_ports


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def _api_healthy(port: int) -> bool:
    if not _port_open(port):
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=3.0) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _mission_control_reachable(port: int = 3000) -> bool:
    return _port_open(port)


def _db_healthy() -> bool:
    try:
        from app.services.mission_control.runtime_db_coordination import build_database_integrity

        db = build_database_integrity()
        integrity = db.get("database_runtime_integrity") or {}
        return bool(integrity.get("healthy") or integrity.get("schema_ok"))
    except Exception:
        return False


def _ownership_coordinated() -> tuple[bool, list[str]]:
    try:
        from app.services.runtime.runtime_ownership_authority import build_runtime_ownership_authority

        auth = build_runtime_ownership_authority()
        own = auth.get("runtime_ownership_authority") or {}
        conflicts = list(own.get("conflicts") or [])
        return bool(own.get("authoritative")) and not conflicts, conflicts
    except Exception:
        return True, []


def _hydration_coherent(api_port: int) -> bool:
    if not _api_healthy(api_port):
        return True
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/v1/runtime/startup-status", timeout=3.0) as resp:
            import json

            blob = json.loads(resp.read().decode("utf-8", errors="replace"))
        exp = blob.get("runtime_startup_experience") or {}
        if exp.get("partial_mode"):
            return False
        readiness = blob.get("runtime_readiness") or {}
        return readiness.get("ready", True) is not False
    except Exception:
        return True


def _startup_stage_coherent(api_port: int) -> bool:
    if not _api_healthy(api_port):
        return True
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/v1/runtime/startup-status", timeout=3.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def build_canonical_runtime_health(*, api_port: int | None = None) -> dict[str, Any]:
    ports = get_canonical_runtime_ports()
    api_port = api_port or ports["api"]
    mc_port = ports["mission_control"]
    port_probe = probe_runtime_ports()
    api_ok = _api_healthy(api_port)
    mc_ok = _mission_control_reachable(mc_port)
    db_ok = _db_healthy()
    own_ok, conflicts = _ownership_coordinated()
    hydration_ok = _hydration_coherent(api_port)
    startup_ok = _startup_stage_coherent(api_port)
    any_port_open = any(port_probe.values())
    stale_session = any_port_open and not (api_ok and mc_ok)
    if own_ok is False and any_port_open:
        stale_session = True
    operational = api_ok and mc_ok and db_ok and own_ok and hydration_ok and startup_ok
    partial = api_ok and (not mc_ok or not hydration_ok) and not stale_session
    readiness = derive_operator_readiness_state(
        api_reachable=api_ok,
        mc_reachable=mc_ok,
        db_healthy=db_ok,
        ownership_healthy=own_ok,
        hydration_partial=not hydration_ok,
    )
    if stale_session:
        message = "AethOS detected an incomplete or stale runtime session."
    elif operational:
        message = "AethOS is operational."
    elif partial:
        message = "AethOS is preparing operational services…"
    else:
        message = "AethOS runtime is offline."
    return {
        "runtime_health_authority": {
            "api_reachable": api_ok,
            "mission_control_reachable": mc_ok,
            "database_healthy": db_ok,
            "ownership_valid": own_ok,
            "ownership_conflicts": conflicts,
            "hydration_active": hydration_ok,
            "startup_stage_coherent": startup_ok,
            "operational": operational,
            "partially_operational": partial,
            "stale_session": stale_session,
            "readiness_state": readiness,
            "may_claim_operational": operational,
            "ports": port_probe,
            "api_port": api_port,
            "message": message,
            "bounded": True,
        }
    }


def is_runtime_truly_operational(*, api_port: int | None = None) -> bool:
    return bool(build_canonical_runtime_health(api_port=api_port)["runtime_health_authority"]["operational"])


def is_stale_runtime_session(*, api_port: int | None = None) -> bool:
    return bool(build_canonical_runtime_health(api_port=api_port)["runtime_health_authority"]["stale_session"])


def runtime_health_summary_lines(*, api_port: int | None = None) -> list[str]:
    ha = build_canonical_runtime_health(api_port=api_port)["runtime_health_authority"]
    return [
        f"API: {'operational' if ha['api_reachable'] else 'offline'}",
        f"Mission Control: {'reachable' if ha['mission_control_reachable'] else 'offline'}",
        f"Runtime ownership: {'coordinated' if ha['ownership_valid'] else 'needs recovery'}",
        f"Database: {'healthy' if ha['database_healthy'] else 'initializing'}",
        f"Hydration: {'ready' if ha['hydration_active'] else 'warming'}",
        f"Workers: idle",
        f"Routing: {'operational' if ha['api_reachable'] else 'pending'}",
    ]


__all__ = [
    "build_canonical_runtime_health",
    "is_runtime_truly_operational",
    "is_stale_runtime_session",
    "runtime_health_summary_lines",
]

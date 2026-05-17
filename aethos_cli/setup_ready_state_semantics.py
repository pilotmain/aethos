# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Ready-state semantics — never claim operational readiness prematurely."""

from __future__ import annotations

from typing import Any


def _check_ok(health: dict[str, Any], name: str) -> bool:
    for c in health.get("checks") or []:
        if c.get("name") == name:
            return bool(c.get("ok"))
    return False


def evaluate_setup_readiness(
    *,
    health: dict[str, Any],
    truly_operational: bool | None = None,
    mission_control_expected: bool = True,
    startup_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_ok = _check_ok(health, "api_health")
    mc_ok = _check_ok(health, "mission_control")
    config_ok = bool(health.get("all_critical_ok"))
    sr = startup_result or {}
    db_ok = sr.get("database_healthy", True)
    own_ok = sr.get("ownership_healthy", True)
    hydration_ok = api_ok or not sr.get("started")
    running = (
        truly_operational
        if truly_operational is not None
        else (api_ok and (mc_ok or not mission_control_expected) and db_ok and own_ok and hydration_ok)
    )
    return {
        "configuration_complete": config_ok,
        "api_reachable": api_ok,
        "mission_control_reachable": mc_ok,
        "database_healthy": db_ok,
        "ownership_healthy": own_ok,
        "truly_operational": running,
        "may_claim_ready": running,
        "may_claim_mission_control_ready": running and mc_ok,
    }


def build_setup_completion_card(
    *,
    health: dict[str, Any],
    api_base: str,
    bag: dict[str, Any],
    truly_operational: bool | None = None,
    mission_control_expected: bool = True,
    startup_result: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    sr = startup_result or bag.get("startup_result") or {}
    state = evaluate_setup_readiness(
        health=health,
        truly_operational=truly_operational,
        mission_control_expected=mission_control_expected,
        startup_result=sr,
    )
    mc = "http://localhost:3000"
    api = api_base.rstrip("/")
    routing = bag.get("routing_summary", "configured")

    if state["may_claim_ready"]:
        title = "AethOS is operational"
        lines = [
            "Mission Control is ready." if state["may_claim_mission_control_ready"] else "API is running.",
            f"Mission Control: {mc}",
            f"API: {api}",
            f"API docs: {api}/docs",
            f"Routing: {routing}",
            "Open: aethos open",
            "Stop: aethos stop",
            "Restart: aethos restart",
            "Status: aethos status",
        ]
        return title, lines

    title = "Preparing operational services…"
    lines = [
        "AethOS is not fully operational yet.",
        f"Routing: {routing}",
        "Start now: aethos start",
        "Status: aethos status",
        "Repair: aethos setup repair",
        "Docs: docs/ENTERPRISE_SETUP.md",
    ]
    if sr.get("stale_session") or (sr.get("api_reachable") and not sr.get("mission_control_reachable")):
        lines.insert(1, "AethOS detected an incomplete or stale runtime session — recovery runs automatically with `aethos start`.")
    return title, lines


__all__ = ["build_setup_completion_card", "evaluate_setup_readiness"]

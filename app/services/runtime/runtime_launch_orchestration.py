# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Canonical first-launch operational orchestration — unified stages, readiness, recovery."""

from __future__ import annotations

import os
from typing import Any

UNIFIED_LAUNCH_STAGES: tuple[tuple[str, str], ...] = (
    ("coordination", "Coordinating operational runtime"),
    ("database", "Validating database integrity"),
    ("authority", "Establishing runtime authority"),
    ("api", "Starting API services"),
    ("mission_control", "Starting Mission Control"),
    ("warmup", "Warming operational intelligence"),
    ("workspace", "Preparing operator workspace"),
    ("readiness", "Verifying enterprise readiness"),
)

OPERATOR_READINESS_STATES: tuple[str, ...] = (
    "initializing",
    "warming",
    "partially_operational",
    "operational",
    "degraded",
    "recovering",
    "maintenance",
)

OFFICE_HOME_INTRO = (
    "Office is your operational command center. "
    "Track runtime health, workers, memory, governance, and active execution here."
)

WARMUP_SERVICE_LABELS: tuple[tuple[str, str], ...] = (
    ("api", "API operational"),
    ("mission_control", "Mission Control operational"),
    ("runtime_truth", "Runtime intelligence warming"),
    ("workers", "Worker coordination preparing"),
    ("memory", "Operational memory syncing"),
    ("routing", "Routing operational"),
)


def launch_stage_count() -> int:
    return len(UNIFIED_LAUNCH_STAGES)


def launch_stages_as_dicts() -> list[dict[str, str]]:
    return [{"id": sid, "label": label} for sid, label in UNIFIED_LAUNCH_STAGES]


def derive_operator_readiness_state(
    *,
    api_reachable: bool = False,
    mc_reachable: bool = False,
    db_healthy: bool = False,
    ownership_healthy: bool = True,
    hydration_partial: bool = True,
    recovering: bool = False,
    degraded: bool = False,
) -> str:
    if recovering:
        return "recovering"
    if degraded:
        return "degraded"
    if not api_reachable:
        return "initializing"
    if not db_healthy or not ownership_healthy:
        if mc_reachable and hydration_partial:
            return "partially_operational"
        return "warming"
    if hydration_partial or not mc_reachable:
        return "partially_operational"
    return "operational"


def build_service_visibility_checklist(
    *,
    api_reachable: bool = False,
    mc_reachable: bool = False,
    db_healthy: bool = False,
    hydration_partial: bool = True,
    workers_idle: bool = True,
    routing_operational: bool = False,
) -> list[str]:
    routing_operational = routing_operational or api_reachable
    lines = [
        f"API: {'operational' if api_reachable else 'starting…'}",
        f"Mission Control: {'reachable' if mc_reachable else 'starting…'}",
        f"Database: {'healthy' if db_healthy else 'initializing'}",
        f"Runtime truth: {'warming' if hydration_partial and api_reachable else ('ready' if api_reachable else 'pending')}",
        f"Workers: {'idle' if workers_idle else 'active'}",
        f"Routing: {'operational' if routing_operational else 'pending'}",
        f"Memory: {'syncing' if hydration_partial and api_reachable else ('ready' if api_reachable else 'pending')}",
    ]
    return lines


def build_warmup_awareness_payload(
    *,
    api_reachable: bool = False,
    mc_reachable: bool = False,
    hydration_partial: bool = True,
    readiness_percent: float = 0.0,
    current_stage_id: str | None = None,
) -> dict[str, Any]:
    checklist: list[dict[str, Any]] = []
    for sid, label in WARMUP_SERVICE_LABELS:
        if sid == "api":
            complete = api_reachable
        elif sid == "mission_control":
            complete = mc_reachable
        elif sid in ("runtime_truth", "workers", "memory"):
            complete = api_reachable and not hydration_partial
        else:
            complete = api_reachable
        checklist.append({"id": sid, "label": label, "complete": complete, "warming": api_reachable and not complete})
    stage = next((s for s in launch_stages_as_dicts() if s["id"] == current_stage_id), launch_stages_as_dicts()[-1])
    return {
        "runtime_warmup_awareness": {
            "headline": "AethOS is preparing operational services…",
            "readiness_percent": round(readiness_percent, 3),
            "current_stage": stage,
            "checklist": checklist,
            "partial_mode": hydration_partial or not mc_reachable,
            "office_primary_entry": True,
            "bounded": True,
        }
    }


def build_startup_recovery_copy(*, issue: str | None = None) -> str:
    base = "AethOS detected a runtime coordination issue. Attempting recovery…"
    if not issue:
        return base
    low = issue.lower()
    if "port" in low or "address already in use" in low:
        return f"{base}\nA service port is in use — try `aethos doctor` or `aethos runtime recover`."
    if "database" in low or "db" in low:
        return f"{base}\nDatabase coordination needs attention — try `aethos doctor`."
    return f"{base}\nTry `aethos doctor` or `aethos runtime recover`."


def build_operator_startup_actions(*, operational: bool = False, recovering: bool = False) -> list[str]:
    if operational:
        return ["Open Mission Control", "Continue to Office", "View diagnostics"]
    if recovering:
        return ["Retry", "Continue warming", "Open Mission Control anyway", "Repair runtime", "View diagnostics"]
    return [
        "Retry",
        "Continue warming",
        "Open Mission Control anyway",
        "Repair runtime",
        "View diagnostics",
    ]


def resolve_browser_launch_url(
    *,
    truly_operational: bool = False,
    mc_reachable: bool = False,
    first_run_onboarding_pending: bool = False,
    guided_tour_requested: bool = False,
) -> str | None:
    if not mc_reachable:
        return None
    if not truly_operational:
        return None
    if first_run_onboarding_pending:
        return "http://localhost:3000/mission-control/onboarding"
    if guided_tour_requested:
        return "http://localhost:3000/mission-control/onboarding"
    return "http://localhost:3000/mission-control/office"


def should_auto_open_browser(
    *,
    truly_operational: bool = False,
    mc_reachable: bool = False,
    api_reachable: bool = False,
    onboarding_state_loaded: bool = True,
) -> bool:
    if os.environ.get("AETHOS_NO_BROWSER", "").strip().lower() in ("1", "true", "yes"):
        return False
    return bool(truly_operational and mc_reachable and api_reachable and onboarding_state_loaded)


def print_unified_launch_header() -> None:
    from aethos_cli.ui import print_info

    print_info("AethOS Runtime Starting…")


def print_unified_launch_completion(result: dict[str, Any]) -> None:
    from aethos_cli.ui import print_box, print_info, print_success

    truly = bool(result.get("truly_operational"))
    mc_url = result.get("mission_control_url") or "http://localhost:3000/mission-control/office"
    readiness = result.get("readiness_state") or "warming"
    if truly:
        print_success("AethOS is operational.")
        print_info(f"Mission Control:\n{mc_url}")
    else:
        print_info(result.get("message") or "AethOS is preparing operational services…")
    print_box("Operational status", result.get("visibility") or build_service_visibility_checklist())
    actions = build_operator_startup_actions(operational=truly)
    if not truly:
        print_box("Operator actions", actions)
    print_info(f"Readiness: {readiness}")


def finalize_first_launch_experience(
    result: dict[str, Any],
    *,
    interactive: bool = True,
    auto_open: bool = True,
) -> dict[str, Any]:
    """Post-start: tour prompt, disciplined browser open, calm completion copy."""
    from aethos_cli.setup_completion_guidance import (
        load_tour_state,
        prompt_guided_first_run_tour,
        try_open_mission_control,
    )

    try:
        from app.services.setup.first_run_operator_onboarding import needs_first_run_operator_onboarding
    except Exception:
        needs_first_run_operator_onboarding = lambda: False  # noqa: E731

    truly = bool(result.get("truly_operational"))
    mc_ok = bool(result.get("mission_control_reachable"))
    api_ok = bool(result.get("api_reachable"))
    tour = load_tour_state()
    pending_onboarding = needs_first_run_operator_onboarding()
    onboarding_loaded = True

    if interactive and truly and not tour.get("completed") and not tour.get("dismissed"):
        prompt_guided_first_run_tour()
        tour = load_tour_state()

    url = resolve_browser_launch_url(
        truly_operational=truly,
        mc_reachable=mc_ok,
        first_run_onboarding_pending=pending_onboarding,
        guided_tour_requested=bool(tour.get("requested")),
    )
    opened = False
    if auto_open and url and should_auto_open_browser(
        truly_operational=truly,
        mc_reachable=mc_ok,
        api_reachable=api_ok,
        onboarding_state_loaded=onboarding_loaded,
    ):
        opened = try_open_mission_control(mc_url=url)

    result = {
        **result,
        "browser_launch_url": url,
        "browser_opened": opened,
        "first_run_onboarding_pending": pending_onboarding,
    }
    print_unified_launch_completion(result)
    return result


def build_runtime_continuity_message(*, restarting: bool = True) -> str:
    if restarting:
        return "Restoring previous operational session…"
    return "AethOS is coming online."


__all__ = [
    "OFFICE_HOME_INTRO",
    "OPERATOR_READINESS_STATES",
    "UNIFIED_LAUNCH_STAGES",
    "build_operator_startup_actions",
    "build_runtime_continuity_message",
    "build_service_visibility_checklist",
    "build_startup_recovery_copy",
    "build_warmup_awareness_payload",
    "derive_operator_readiness_state",
    "finalize_first_launch_experience",
    "launch_stage_count",
    "launch_stages_as_dicts",
    "print_unified_launch_completion",
    "print_unified_launch_header",
    "resolve_browser_launch_url",
    "should_auto_open_browser",
]

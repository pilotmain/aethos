# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Authoritative runtime recovery coordinator (Phase 4 Step 25)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.runtime_ownership_authority import build_runtime_ownership_authority
from app.services.runtime.runtime_process_group_manager import (
    build_process_group_status,
    restart_runtime_process_groups,
    terminate_runtime_process_groups,
)


def execute_runtime_recovery(*, clean: bool = False, restart: bool = True) -> dict[str, Any]:
    """Coordinate DB, hydration, process, and ownership recovery."""
    from app.services.mission_control.runtime_db_coordination import (
        build_database_integrity,
        ensure_schema_with_recovery,
    )
    from app.services.runtime.runtime_truth_ownership_lock import release_truth_hydration_lock_if_owner

    actions: list[str] = []
    stop = terminate_runtime_process_groups(force=clean)
    actions.append("process_groups_stopped")
    release_truth_hydration_lock_if_owner()
    actions.append("truth_lock_released")
    schema = ensure_schema_with_recovery()
    if schema.get("ok"):
        actions.append("schema_recovered")
    db = build_database_integrity()
    ownership = build_runtime_ownership_authority()
    conflicts = (ownership.get("runtime_process_conflicts") or {}).get("items") or []

    restart_result: dict[str, Any] | None = None
    if restart:
        restart_result = restart_runtime_process_groups(clean=clean)
        if restart_result.get("ok"):
            actions.append("api_restarted")

    confidence = 0.92 if not conflicts and schema.get("ok") else (0.7 if schema.get("ok") else 0.5)
    ok = schema.get("ok") and (restart_result is None or restart_result.get("ok", True))
    return {
        "ok": ok,
        "message": (
            "Enterprise runtime coordination recovered successfully."
            if ok
            else "Runtime coordination recovered partially — review conflicts with `aethos runtime ownership`."
        ),
        "runtime_recovery_authority": {
            "phase": "phase4_step25",
            "authoritative": ok,
            "actions_taken": actions,
            "conflicts_remaining": len(conflicts),
            "bounded": True,
        },
        "runtime_recovery_integrity": {
            "phase": "phase4_step25",
            "schema_ok": bool(schema.get("ok")),
            "process_stop_ok": bool(stop.get("ok")),
            "bounded": True,
        },
        "runtime_recovery_actions": {"items": actions, "count": len(actions)},
        "runtime_recovery_confidence": {"score": round(confidence, 3), "calm": True},
        "database_recovery": db.get("database_runtime_integrity"),
        "stop": stop,
        "restart": restart_result,
    }


def build_runtime_recovery_authority(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    ownership = build_runtime_ownership_authority(truth)
    conflicts = (ownership.get("runtime_process_conflicts") or {}).get("items") or []
    from app.services.mission_control.runtime_db_coordination import build_database_integrity

    db = build_database_integrity()
    stable = len(conflicts) == 0 and (db.get("database_runtime_integrity") or {}).get("ok", True)
    return {
        "runtime_recovery_authority": {
            "phase": "phase4_step25",
            "authoritative": stable,
            "recovery_ready": True,
            "recommended": "aethos runtime recover" if conflicts else None,
            "operator_message": (
                "Runtime coordination is stable."
                if stable
                else "AethOS can recover runtime conflicts automatically — run `aethos runtime recover`."
            ),
            "bounded": True,
        },
        "runtime_recovery_integrity": {
            "phase": "phase4_step25",
            "stable": stable,
            "conflict_count": len(conflicts),
            "bounded": True,
        },
        "runtime_recovery_actions": {
            "items": ["recover", "restart --clean", "doctor", "repair"],
            "bounded": True,
        },
        "runtime_recovery_confidence": {
            "score": 0.95 if stable else 0.65,
            "calm": True,
            "bounded": True,
        },
        **build_process_group_status(),
    }

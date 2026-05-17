# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime supervision live model for API and Mission Control (Phase 4 Step 19)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_db_coordination import build_runtime_db_health, get_db_lock_state
from app.services.mission_control.runtime_process_supervision import build_runtime_process_supervision
from app.services.mission_control.runtime_ownership_lock import format_runtime_ownership_summary
from app.services.mission_control.telegram_ownership_ux import build_telegram_ownership_status
from app.services.mission_control.runtime_uvicorn_process import detect_uvicorn_process_kind


def build_runtime_supervision() -> dict[str, Any]:
    try:
        from app.services.runtime.runtime_ownership_authority import build_runtime_ownership_authority

        authority = build_runtime_ownership_authority()
    except Exception:
        authority = {}
    sup = build_runtime_process_supervision()
    tg = build_telegram_ownership_status()
    db_state = get_db_lock_state()
    own = sup.get("runtime_ownership") or {}
    svc = sup.get("runtime_services") or {}
    db = sup.get("runtime_db_health") or {}
    startup = sup.get("runtime_startup_lock") or {}
    conflicts = list((sup.get("runtime_process_supervision") or {}).get("conflicts") or [])

    own_auth = authority.get("runtime_ownership_authority") or {}
    if own_auth.get("conflicts"):
        conflicts = list(conflicts) + list(own_auth.get("conflicts") or [])

    api_owner = "healthy" if own.get("this_process_owns") or own.get("holder_pid") else "observer"
    if conflicts:
        api_owner = "conflict"

    return {
        **sup,
        **tg,
        **authority,
        "runtime_supervision": {
            "phase": "phase4_step25",
            "supervision_verified": True,
            "api_owner_status": api_owner,
            "sqlite_status": "healthy" if db.get("ok") else "degraded",
            "telegram_mode": (tg.get("telegram_ownership") or {}).get("mode"),
            "hydration_lock_clear": startup.get("holder_pid") is None,
            "duplicate_api_processes": max(0, int(svc.get("api_instance_count") or 0) - 1),
            "observer_mode": own.get("observer_mode"),
            "degraded_mode": bool(conflicts) or not db.get("ok"),
            "uvicorn_process_kind": detect_uvicorn_process_kind(),
            "operator_summary": format_runtime_ownership_summary(),
            "ownership_authoritative": bool(own_auth.get("authoritative")),
            "process_conflicts": len(own_auth.get("conflicts") or []),
            "recommended_repairs": (sup.get("runtime_process_supervision") or {}).get("recovery_actions")
            or ["aethos runtime recover", "aethos runtime restart --clean"],
            "db_lock_state": db_state,
            "bounded": True,
        },
    }

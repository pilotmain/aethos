# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Single authoritative runtime ownership coordinator (Phase 4 Step 25)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_db_coordination import build_database_integrity
from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status
from app.services.mission_control.runtime_process_supervision import build_runtime_process_supervision
from app.services.mission_control.runtime_service_registry import build_runtime_service_registry
from app.services.mission_control.runtime_uvicorn_process import detect_uvicorn_process_kind


def build_runtime_ownership_authority(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    ownership = build_runtime_ownership_status()
    services = build_runtime_service_registry()
    supervision = build_runtime_process_supervision()
    own = ownership.get("runtime_ownership") or {}
    svc = services.get("runtime_services") or {}
    proc_sup = supervision.get("runtime_process_supervision") or {}
    conflicts: list[str] = list(proc_sup.get("conflicts") or [])

    if own.get("stale_owner"):
        conflicts.append("stale ownership lock on disk")
    if own.get("duplicate_ownership_risk"):
        conflicts.append("telegram and API ownership split across processes")
    if int(svc.get("api_instance_count") or 0) > 1:
        conflicts.append("duplicate API processes")
    if svc.get("duplicate_telegram_poller_risk"):
        conflicts.append("embedded and standalone Telegram pollers")
    uvicorn_kind = detect_uvicorn_process_kind()
    if uvicorn_kind == "reloader_parent":
        conflicts.append("uvicorn reload parent should not hold runtime ownership")

    authoritative = not conflicts and (
        own.get("this_process_owns") or own.get("observer_mode") or not own.get("holder_pid")
    )
    return {
        "runtime_ownership_authority": {
            "phase": "phase4_step25",
            "authoritative": authoritative,
            "single_owner_enforced": len(conflicts) == 0,
            "holder_pid": own.get("holder_pid"),
            "holder_role": own.get("holder_role"),
            "uvicorn_process_kind": uvicorn_kind,
            "api_instance_count": svc.get("api_instance_count"),
            "conflicts": conflicts,
            "message": (
                "Runtime ownership is authoritative."
                if authoritative
                else "Runtime ownership conflicts detected — run `aethos runtime recover`."
            ),
            "bounded": True,
        },
        "runtime_process_authority": {
            "phase": "phase4_step25",
            "process_supervision_locked": True,
            "api_instances": svc.get("api_instance_count"),
            "telegram_instances": svc.get("telegram_instance_count"),
            "reloader_parents_filtered": svc.get("reloader_parents_filtered"),
            "recommended_action": svc.get("recommended_action"),
            "bounded": True,
        },
        "runtime_supervision_authority": {
            "phase": "phase4_step25",
            "supervision_verified": bool(truth.get("runtime_supervision_verified")),
            "recovery_actions": proc_sup.get("recovery_actions") or [
                "aethos runtime recover",
                "aethos runtime restart --clean",
                "aethos doctor",
            ],
            "bounded": True,
        },
        "runtime_process_integrity": {
            "phase": "phase4_step25",
            "integrity_ok": len(conflicts) == 0,
            "conflict_count": len(conflicts),
            "bounded": True,
        },
        "runtime_process_conflicts": {
            "phase": "phase4_step25",
            "items": conflicts,
            "count": len(conflicts),
            "bounded": True,
        },
        **build_database_integrity(),
    }

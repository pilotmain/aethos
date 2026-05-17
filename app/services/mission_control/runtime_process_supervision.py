# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime process supervision bundle (Phase 4 Step 18)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_db_coordination import build_runtime_db_health
from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status
from app.services.mission_control.runtime_service_registry import (
    build_runtime_processes,
    build_runtime_service_registry,
)
from app.services.mission_control.runtime_startup_coordination import build_startup_lock_status


def build_runtime_process_supervision() -> dict[str, Any]:
    ownership = build_runtime_ownership_status()
    services = build_runtime_service_registry()
    processes = build_runtime_processes()
    db = build_runtime_db_health()
    startup = build_startup_lock_status()
    own = ownership.get("runtime_ownership") or {}
    svc = services.get("runtime_services") or {}
    conflicts: list[str] = []
    if own.get("duplicate_ownership_risk"):
        conflicts.append("runtime ownership and telegram polling held by different live processes")
    if svc.get("api_instance_count", 0) > 1:
        conflicts.append("multiple API processes detected")
    if svc.get("duplicate_telegram_poller_risk"):
        conflicts.append("embedded API and standalone Telegram bot may both poll")
    if not (db.get("runtime_db_health") or {}).get("ok"):
        conflicts.append("database health check failed — sqlite may be locked")
    return {
        **ownership,
        **services,
        **processes,
        **db,
        **startup,
        "runtime_process_supervision": {
            "phase": "phase4_step19",
            "process_supervision_locked": True,
            "observer_mode": own.get("observer_mode"),
            "conflicts": conflicts,
            "recovery_actions": [
                "aethos runtime takeover",
                "aethos runtime release",
                "aethos restart runtime",
                "aethos doctor",
            ],
            "bounded": True,
        },
    }

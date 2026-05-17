# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime service registry — discover local API/web/bot processes (Phase 4 Step 18)."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from app.services.mission_control.runtime_ownership_lock import record_process_lifecycle_event


def _pgrep(pattern: str) -> list[dict[str, Any]]:
    try:
        out = subprocess.run(
            ["pgrep", "-fl", pattern],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows: list[dict[str, Any]] = []
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if not parts:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        rows.append({"pid": pid, "command": parts[1] if len(parts) > 1 else pattern})
    return rows


def build_runtime_service_registry() -> dict[str, Any]:
    api_port = os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010"
    services = {
        "api": _pgrep("uvicorn app.main:app"),
        "telegram_bot": _pgrep("app.bot.telegram_bot"),
        "mission_control_web": _pgrep("next dev"),
    }
    embedded = [p for p in services["api"] if "reload" in (p.get("command") or "")]
    standalone_bot = services["telegram_bot"]
    duplicate_poller = len(standalone_bot) > 0 and any(
        "embed" in (a.get("command") or "").lower() for a in services["api"]
    )
    registry = {
        "runtime_services": {
            "api_port": api_port,
            "services": services,
            "api_instance_count": len(services["api"]),
            "telegram_instance_count": len(standalone_bot),
            "web_instance_count": len(services["mission_control_web"]),
            "embedded_api_detected": bool(embedded),
            "duplicate_telegram_poller_risk": duplicate_poller and len(standalone_bot) > 0,
            "recommended_action": None,
            "bounded": True,
        }
    }
    if registry["runtime_services"]["api_instance_count"] > 1:
        registry["runtime_services"]["recommended_action"] = "Stop duplicate API processes: aethos restart runtime"
    elif registry["runtime_services"]["duplicate_telegram_poller_risk"]:
        registry["runtime_services"]["recommended_action"] = (
            "Run only embedded API bot or standalone bot — not both"
        )
    record_process_lifecycle_event("registry_scan", detail="service registry built")
    return registry


def build_runtime_processes() -> dict[str, Any]:
    reg = build_runtime_service_registry()["runtime_services"]
    processes: list[dict[str, Any]] = []
    for kind, rows in (reg.get("services") or {}).items():
        for row in rows:
            processes.append({"kind": kind, **row})
    return {
        "runtime_processes": {
            "processes": processes,
            "count": len(processes),
            "supervision": "advisory",
            "bounded": True,
        }
    }

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Aggregate deployment + environment health for runtime APIs."""

from __future__ import annotations

from typing import Any

from app.deployments.deployment_registry import deployment_records, list_deployments_for_user
from app.environments import environment_registry


def deployment_health_summary(st: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    uid = (user_id or "").strip()
    rows = list_deployments_for_user(st, uid) if uid else [r for r in deployment_records(st).values() if isinstance(r, dict)]
    by_status: dict[str, int] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        stt = str(r.get("status") or "unknown")
        by_status[stt] = by_status.get(stt, 0) + 1
    rollback_active = sum(
        1 for r in rows if isinstance(r, dict) and str((r.get("rollback") or {}).get("status")) == "running"
    )
    return {
        "deployment_count": len(rows),
        "by_status": by_status,
        "rollback_active": rollback_active,
    }


def environment_health_bridge(st: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    uid = (user_id or "").strip()
    if uid:
        envs = environment_registry.list_environments_for_user(st, uid)
    else:
        envs = list(environment_registry.iter_environments(st))
    degraded = sum(1 for e in envs if isinstance(e, dict) and str(e.get("status") or "") == "degraded")
    failed = sum(1 for e in envs if isinstance(e, dict) and str(e.get("status") or "") == "failed")
    return {"environment_count": len(envs), "degraded": degraded, "failed": failed}

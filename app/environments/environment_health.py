# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Environment status transitions (``healthy`` | ``degraded`` | …)."""

from __future__ import annotations

from typing import Any

from app.environments.environment_registry import ensure_environment, get_environment
from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import utc_now_iso


def set_status(st: dict[str, Any], environment_id: str, status: str, *, reason: str = "") -> dict[str, Any] | None:
    row = ensure_environment(st, str(environment_id))
    prev = str(row.get("status") or "")
    ts = utc_now_iso()
    row["status"] = str(status)[:32]
    row["updated_at"] = ts
    if reason:
        row["last_reason"] = str(reason)[:2000]
    orchestration_log.append_json_log(
        "environments",
        "environment_status",
        environment_id=str(environment_id),
        status=row["status"],
        previous=prev,
    )
    if status == "failed":
        emit_runtime_event(
            st,
            "environment_failed",
            environment_id=str(environment_id),
            user_id=str(row.get("user_id") or ""),
            status=status,
        )
    return row


def note_deployment_outcome(st: dict[str, Any], environment_id: str, *, success: bool) -> None:
    row = get_environment(st, environment_id)
    if not row:
        return
    m = row.setdefault("metrics", {})
    if not isinstance(m, dict):
        row["metrics"] = {}
        m = row["metrics"]
    if success:
        m["deployment_success"] = int(m.get("deployment_success") or 0) + 1
        row["status"] = "healthy"
    else:
        m["deployment_failure"] = int(m.get("deployment_failure") or 0) + 1
        row["status"] = "degraded"
    row["updated_at"] = utc_now_iso()

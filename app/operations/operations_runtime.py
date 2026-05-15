# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational workflow queue (deploy, rollback, health_check, …) in runtime JSON."""

from __future__ import annotations

import uuid
from typing import Any

from app.environments.environment_registry import default_environment_id_for_user
from app.orchestration import orchestration_log
from app.runtime.runtime_state import utc_now_iso


_ALLOWED = frozenset({"deploy", "rollback", "restart", "repair", "cleanup", "backup", "restore", "health_check"})


def operational_workflows(st: dict[str, Any]) -> list[Any]:
    ow = st.setdefault("operational_workflows", [])
    if not isinstance(ow, list):
        st["operational_workflows"] = []
        return st["operational_workflows"]
    return ow


def enqueue_operation(
    st: dict[str, Any],
    op_type: str,
    *,
    user_id: str,
    environment_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ot = str(op_type or "").strip().lower()
    if ot not in _ALLOWED:
        raise ValueError(f"unsupported operation type: {op_type}")
    eid = environment_id or default_environment_id_for_user(st, user_id)
    ts = utc_now_iso()
    oid = f"op_{uuid.uuid4().hex[:12]}"
    rec: dict[str, Any] = {
        "operation_id": oid,
        "type": ot,
        "status": "queued",
        "user_id": str(user_id),
        "environment_id": str(eid),
        "created_at": ts,
        "updated_at": ts,
        "payload": dict(payload or {}),
    }
    operational_workflows(st).append(rec)
    orchestration_log.append_json_log("operations", "operation_enqueued", operation_id=oid, op_type=ot, environment_id=eid)
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["operational_workflow_total"] = int(m.get("operational_workflow_total") or 0) + 1
    return rec


def list_operations(st: dict[str, Any], *, user_id: str, limit: int = 80) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    out: list[dict[str, Any]] = []
    for row in reversed(operational_workflows(st)):
        if not isinstance(row, dict):
            continue
        if uid and str(row.get("user_id") or "") != uid:
            continue
        out.append(dict(row))
        if len(out) >= limit:
            break
    return out

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mark in-flight deployments after process restart (safe continuation hints)."""

from __future__ import annotations

from typing import Any

from app.deployments.deployment_registry import deployment_records, upsert_deployment
from app.orchestration import orchestration_log
from app.runtime.runtime_state import utc_now_iso


def recover_deployments_on_boot(st: dict[str, Any]) -> dict[str, Any]:
    """Running deployments become ``recovering`` until the next supervisor tick."""
    n = 0
    for did, row in list(deployment_records(st).items()):
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") != "running":
            continue
        ts = utc_now_iso()
        upsert_deployment(
            st,
            str(did),
            {"status": "recovering", "updated_at": ts, "recovery": {"boot": ts, "note": "process_restart"}},
        )
        orchestration_log.append_json_log(
            "deployment_recovery",
            "deployment_recovering",
            deployment_id=str(did),
            environment_id=str(row.get("environment_id") or ""),
        )
        n += 1
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["deployment_recovery_boot_total"] = int(m.get("deployment_recovery_boot_total") or 0) + n
    return {"deployments_marked_recovering": n}

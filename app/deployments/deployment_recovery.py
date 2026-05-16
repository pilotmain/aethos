# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mark in-flight deployments after process restart (safe continuation hints)."""

from __future__ import annotations

from typing import Any

from app.deployments.deployment_registry import deployment_records, upsert_deployment
from app.deployments.deployment_stages import is_terminal_stage
from app.environments.environment_locks import repair_stale_locks
from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import utc_now_iso


def recover_deployments_on_boot(st: dict[str, Any]) -> dict[str, Any]:
    """Running deployments become ``recovering`` until the next supervisor tick; repair locks + rollback hints."""
    lk = repair_stale_locks(st)
    n = 0
    rb_n = 0
    for did, row in list(deployment_records(st).items()):
        if not isinstance(row, dict):
            continue
        rb = row.get("rollback") if isinstance(row.get("rollback"), dict) else {}
        if str(rb.get("status") or "") == "running":
            ts = utc_now_iso()
            rb2 = dict(rb)
            rb2["status"] = "recovering"
            rb2["updated_at"] = ts
            rec = dict(row.get("recovery") or {})
            rec["rollback_boot"] = ts
            upsert_deployment(
                st,
                str(did),
                {"rollback": rb2, "status": "recovering", "updated_at": ts, "recovery": rec},
            )
            orchestration_log.append_json_log(
                "deployment_recovery",
                "rollback_recovering",
                deployment_id=str(did),
                environment_id=str(row.get("environment_id") or ""),
            )
            emit_runtime_event(
                st,
                "deployment_recovered",
                deployment_id=str(did),
                environment_id=str(row.get("environment_id") or ""),
                kind="rollback",
            )
            rb_n += 1
            continue
        if str(row.get("status") or "") != "running":
            continue
        stg = str(row.get("deployment_stage") or "")
        if is_terminal_stage(stg):
            continue
        ts = utc_now_iso()
        rec = dict(row.get("recovery") or {})
        rec["boot"] = ts
        rec["note"] = "process_restart"
        upsert_deployment(
            st,
            str(did),
            {"status": "recovering", "updated_at": ts, "recovery": rec},
        )
        orchestration_log.append_json_log(
            "deployment_recovery",
            "deployment_recovering",
            deployment_id=str(did),
            environment_id=str(row.get("environment_id") or ""),
        )
        emit_runtime_event(
            st,
            "deployment_recovered",
            deployment_id=str(did),
            environment_id=str(row.get("environment_id") or ""),
            kind="deployment",
        )
        n += 1
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["deployment_recovery_boot_total"] = int(m.get("deployment_recovery_boot_total") or 0) + n
    try:
        from app.runtime import runtime_reliability

        runtime_reliability.bump_successful_recoveries(st, int(n) + int(rb_n))
    except Exception:
        pass
    return {
        "deployments_marked_recovering": n,
        "rollback_recoveries": rb_n,
        "locks_repaired": int(lk.get("locks_repaired") or 0),
    }

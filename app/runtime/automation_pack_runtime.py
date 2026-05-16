# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Automation pack execution runtime — bounded, operator-triggered (Phase 3 Step 10)."""

from __future__ import annotations

import uuid
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_EXECUTION_HISTORY = 48
_MAX_PACK_RUNTIME_ENTRIES = 64

_PACK_CAPABILITY_MAP: dict[str, list[str]] = {
    "deployment": ["deployment_automation", "rollback"],
    "repair": ["repair_automation", "fix_and_redeploy"],
    "monitoring": ["operational_summaries", "provider_diagnostics"],
    "workspace_maintenance": ["workspace_audits", "runtime_cleanup"],
    "provider_diagnostics": ["provider_diagnostics"],
    "project_onboarding": ["continuity_workflows"],
    "research": ["research_automation"],
    "custom": ["operational_summaries"],
}


def ensure_automation_pack_runtime_schema(st: dict[str, Any]) -> None:
    if not isinstance(st.get("automation_pack_runtime"), dict):
        st["automation_pack_runtime"] = {}
    if not isinstance(st.get("automation_pack_executions"), dict):
        st["automation_pack_executions"] = {}


def enrich_pack_runtime_row(base: dict[str, Any]) -> dict[str, Any]:
    """Augment pack list row with Step 10 runtime fields."""
    st = load_runtime_state()
    ensure_automation_pack_runtime_schema(st)
    pid = str(base.get("plugin_id") or "")
    runtime = (st.get("automation_pack_runtime") or {}).get(pid) or {}
    pack_type = str(base.get("pack_type") or "custom")
    executions = _execution_history_for_pack(pid)
    return {
        **base,
        "pack_id": pid,
        "capabilities": runtime.get("capabilities") or _PACK_CAPABILITY_MAP.get(pack_type, ["operational_summaries"]),
        "trust_tier": runtime.get("trust_tier") or ("verified" if base.get("verified") else "community"),
        "execution_scope": runtime.get("execution_scope") or "operator_triggered",
        "execution_history": executions[:8],
        "runtime_health": base.get("health") or "registered",
        "governance_state": runtime.get("governance_state") or ("active" if base.get("enabled") else "disabled"),
        "operational_metrics": {
            "runs_24h": sum(1 for e in executions if _recent(e)),
            "success_rate": _success_rate(executions),
            "last_run_at": executions[0].get("started_at") if executions else None,
        },
    }


def run_automation_pack(
    pack_id: str,
    *,
    operator_id: str = "operator",
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Operator-triggered pack run — records execution; does not spawn hidden workers."""
    from app.plugins.automation_packs import get_automation_pack

    pack = get_automation_pack(pack_id)
    if not pack:
        return {"ok": False, "error": "pack_not_found", "pack_id": pack_id}
    if not pack.get("enabled", True):
        return {"ok": False, "error": "pack_disabled", "pack_id": pack_id}

    st = load_runtime_state()
    ensure_automation_pack_runtime_schema(st)
    eid = f"apex_{uuid.uuid4().hex[:12]}"
    started = utc_now_iso()
    pack_type = str(pack.get("pack_type") or "custom")
    row = {
        "execution_id": eid,
        "pack_id": pack_id,
        "pack_type": pack_type,
        "operator_id": operator_id,
        "params": dict(list((params or {}).items())[:12]),
        "status": "completed",
        "started_at": started,
        "completed_at": utc_now_iso(),
        "trace_chain": ["operator", "orchestrator", "automation_pack", pack_type, "result"],
        "result_summary": f"Pack {pack_id} ({pack_type}) executed under orchestrator control.",
    }
    execs = st.setdefault("automation_pack_executions", {})
    if isinstance(execs, dict):
        execs[eid] = row
        _trim_executions(execs)
    pr = st.setdefault("automation_pack_runtime", {})
    if isinstance(pr, dict):
        pr[pack_id] = {
            "pack_id": pack_id,
            "pack_type": pack_type,
            "capabilities": _PACK_CAPABILITY_MAP.get(pack_type, ["operational_summaries"]),
            "trust_tier": "verified" if pack.get("verified") else "community",
            "execution_scope": "operator_triggered",
            "governance_state": "active",
            "last_execution_id": eid,
            "updated_at": utc_now_iso(),
        }
        if len(pr) > _MAX_PACK_RUNTIME_ENTRIES:
            _trim_dict(pr, _MAX_PACK_RUNTIME_ENTRIES)
    save_runtime_state(st)

    _emit_pack_governance("automation_pack_executed", pack_id=pack_id, execution_id=eid, who=operator_id)
    try:
        from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

        emit_mc_runtime_event(
            "automation_pack_executed",
            pack_id=pack_id,
            execution_id=eid,
            category="automation",
        )
    except Exception:
        pass
    return {"ok": True, "execution": row}


def build_automation_pack_runtime_truth() -> dict[str, Any]:
    from app.plugins.automation_packs import list_automation_packs_with_health

    packs = [enrich_pack_runtime_row(p) for p in list_automation_packs_with_health()]
    st = load_runtime_state()
    execs = st.get("automation_pack_executions") or {}
    recent = []
    if isinstance(execs, dict):
        recent = sorted(
            [r for r in execs.values() if isinstance(r, dict)],
            key=lambda r: str(r.get("started_at") or ""),
            reverse=True,
        )[:16]
    return {"packs": packs, "recent_executions": recent, "pack_count": len(packs)}


def _execution_history_for_pack(pack_id: str) -> list[dict[str, Any]]:
    st = load_runtime_state()
    execs = st.get("automation_pack_executions") or {}
    rows = [
        r
        for r in (execs.values() if isinstance(execs, dict) else [])
        if isinstance(r, dict) and str(r.get("pack_id")) == pack_id
    ]
    rows.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
    return rows[: _MAX_EXECUTION_HISTORY]


def _emit_pack_governance(event_type: str, **fields: Any) -> None:
    try:
        from app.runtime.workspace_operational_memory import record_workspace_governance_event

        record_workspace_governance_event(
            event_type,
            who=str(fields.pop("who", "operator")),
            what=fields.get("execution_id") or fields.get("pack_id") or event_type,
        )
    except Exception:
        pass


def _success_rate(executions: list[dict[str, Any]]) -> float | None:
    if not executions:
        return None
    ok = sum(1 for e in executions if e.get("status") == "completed")
    return round(ok / len(executions), 3)


def _recent(row: dict[str, Any]) -> bool:
    return bool(row.get("started_at"))


def _trim_executions(execs: dict[str, Any]) -> None:
    if len(execs) <= _MAX_EXECUTION_HISTORY:
        return
    ordered = sorted(execs.items(), key=lambda kv: str((kv[1] or {}).get("started_at") or ""))
    for k, _ in ordered[: len(execs) - _MAX_EXECUTION_HISTORY]:
        execs.pop(k, None)


def _trim_dict(d: dict[str, Any], cap: int) -> None:
    if len(d) <= cap:
        return
    ordered = sorted(d.items(), key=lambda kv: str((kv[1] or {}).get("updated_at") or ""))
    for k, _ in ordered[: len(d) - cap]:
        d.pop(k, None)

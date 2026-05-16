# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded operational memory, deliverables, and continuations for runtime workers (Phase 3 Step 7)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_RECENT = 12
_MAX_DELIVERABLES_GLOBAL = 200
_MAX_DELIVERABLES_PER_WORKER = 24
_MAX_CONTINUATIONS = 48


def get_worker_memory_limits() -> dict[str, int]:
    from app.core.config import get_settings

    s = get_settings()
    return {
        "task": int(getattr(s, "aethos_worker_memory_task_limit", _MAX_RECENT)),
        "output": int(getattr(s, "aethos_worker_memory_output_limit", _MAX_RECENT)),
        "deliverable": int(getattr(s, "aethos_worker_deliverable_limit", _MAX_DELIVERABLES_GLOBAL)),
        "continuation": int(getattr(s, "aethos_worker_continuation_limit", _MAX_CONTINUATIONS)),
    }

_DELIVERABLE_TYPES = frozenset(
    {
        "research_summary",
        "deployment_report",
        "repair_summary",
        "verification_report",
        "planning_output",
        "provider_diagnostic",
        "automation_outcome",
        "workflow_summary",
        "general_output",
    }
)


def ensure_worker_intel_schema(st: dict[str, Any]) -> None:
    for key in ("worker_memory", "worker_deliverables", "worker_continuations", "worker_session_context"):
        if not isinstance(st.get(key), dict):
            st[key] = {}


def infer_deliverable_type(*, prompt: str, domain: str, success: bool) -> str:
    p = (prompt or "").lower()
    d = (domain or "").lower()
    if "repair" in p or d in ("ops", "vercel", "railway"):
        if "repair" in p or "fix" in p:
            return "repair_summary"
        if "deploy" in p:
            return "deployment_report"
        return "provider_diagnostic"
    if "research" in p or "competitor" in p or d == "marketing":
        return "research_summary"
    if "verif" in p or "test" in p or d in ("qa", "test"):
        return "verification_report"
    if "plan" in p:
        return "planning_output"
    if "automation" in p:
        return "automation_outcome"
    if "workflow" in p:
        return "workflow_summary"
    return "general_output" if success else "workflow_summary"


def persist_deliverable(
    *,
    worker_id: str,
    task_id: str,
    deliverable_type: str,
    summary: str,
    content: str,
    artifacts: list[str] | None = None,
    provider_context: dict[str, Any] | None = None,
    output_id: str | None = None,
    title: str | None = None,
    project_id: str | None = None,
    status: str = "final",
) -> str:
    st = load_runtime_state()
    ensure_worker_intel_schema(st)
    did = f"dlv_{uuid.uuid4().hex[:12]}"
    dtype = deliverable_type if deliverable_type in _DELIVERABLE_TYPES else "general_output"
    row = {
        "deliverable_id": did,
        "worker_id": worker_id,
        "task_id": task_id,
        "type": dtype,
        "title": (title or summary or dtype)[:120],
        "summary": (summary or "")[:500],
        "content": (content or "")[:16000],
        "artifacts": list(artifacts or [])[:24],
        "provider_context": dict(list((provider_context or {}).items())[:8]),
        "output_id": output_id,
        "project_id": project_id,
        "created_at": utc_now_iso(),
        "status": status,
    }
    try:
        from app.services.mission_control.worker_deliverable_ops import apply_deliverable_privacy

        row = apply_deliverable_privacy(row)
    except Exception:
        pass
    dels = st.setdefault("worker_deliverables", {})
    if isinstance(dels, dict):
        dels[did] = row
        _trim_deliverables(dels)
    mem = _memory_bucket(st, worker_id)
    mem["recent_outputs"] = _push_bounded(mem.get("recent_outputs"), did, _MAX_RECENT)
    if dtype in ("deployment_report", "provider_diagnostic"):
        mem["deployment_history"] = _push_bounded(mem.get("deployment_history"), did, 8)
    if dtype == "repair_summary":
        mem["repair_history"] = _push_bounded(mem.get("repair_history"), did, 8)
    mem["memory_summary"] = _summarize_memory(mem)
    save_runtime_state(st)
    try:
        from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

        emit_mc_runtime_event(
            "worker_deliverable_persisted",
            deliverable_id=did,
            worker_id=worker_id,
            task_id=task_id,
            deliverable_type=dtype,
            status=status,
        )
    except Exception:
        pass
    if dtype == "research_summary":
        try:
            from app.services.research_continuity import ensure_research_deliverable_linked

            prior = None
            prev = list_deliverables_for_worker(worker_id, limit=2)
            if len(prev) >= 2 and prev[1].get("deliverable_id") != did:
                prior = str(prev[1].get("deliverable_id"))
            ensure_research_deliverable_linked(
                deliverable_id=did,
                project_id=project_id,
                worker_id=worker_id,
                topic="research",
                prior_deliverable_id=prior,
            )
        except Exception:
            pass
    return did


def update_worker_memory(
    *,
    worker_id: str,
    task_id: str | None = None,
    output_id: str | None = None,
    failure: str | None = None,
    workspace_snippet: dict[str, Any] | None = None,
    provider_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st = load_runtime_state()
    ensure_worker_intel_schema(st)
    mem = _memory_bucket(st, worker_id)
    limits = get_worker_memory_limits()
    if task_id:
        mem["recent_tasks"] = _push_bounded(mem.get("recent_tasks"), task_id, limits["task"])
    if output_id:
        mem["recent_outputs"] = _push_bounded(mem.get("recent_outputs"), output_id, limits["output"])
    if failure:
        mem["recent_failures"] = _push_bounded(mem.get("recent_failures"), failure[:300], 8)
    if workspace_snippet:
        mem["workspace_context"] = _push_bounded(mem.get("workspace_context"), workspace_snippet, 6)
    if provider_action:
        mem["provider_actions"] = _push_bounded(mem.get("provider_actions"), provider_action, 8)
    mem["memory_summary"] = _summarize_memory(mem)
    save_runtime_state(st)
    return mem


def build_worker_memory(worker_id: str) -> dict[str, Any]:
    st = load_runtime_state()
    ensure_worker_intel_schema(st)
    mem = dict(_memory_bucket(st, worker_id))
    mem["worker_id"] = worker_id
    mem["deliverables"] = list_deliverables_for_worker(worker_id, limit=8)
    return mem


def get_deliverable(deliverable_id: str) -> dict[str, Any] | None:
    st = load_runtime_state()
    dels = st.get("worker_deliverables") or {}
    if isinstance(dels, dict):
        row = dels.get(deliverable_id)
        if isinstance(row, dict):
            return dict(row)
    return None


def list_continuations_for_worker(worker_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
    st = load_runtime_state()
    conts = st.get("worker_continuations") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(conts, dict):
        for row in conts.values():
            if isinstance(row, dict) and str(row.get("worker_id")) == worker_id:
                rows.append(row)
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows[: max(1, min(int(limit), 32))]


def list_deliverables_for_worker(worker_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
    st = load_runtime_state()
    dels = st.get("worker_deliverables") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(dels, dict):
        for row in dels.values():
            if isinstance(row, dict) and str(row.get("worker_id")) == worker_id:
                rows.append(row)
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows[: max(1, min(int(limit), 32))]


def search_deliverables(
    *,
    query: str | None = None,
    worker_id: str | None = None,
    deliverable_type: str | None = None,
    handle: str | None = None,
    task_id: str | None = None,
    project_id: str | None = None,
    provider: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 16,
) -> list[dict[str, Any]]:
    if handle and not worker_id:
        from app.runtime.agent_work_state import find_runtime_agent_by_handle

        rt = find_runtime_agent_by_handle(handle)
        if rt:
            worker_id = str(rt.get("agent_id"))
    st = load_runtime_state()
    dels = st.get("worker_deliverables") or {}
    q = (query or "").lower()
    rows: list[dict[str, Any]] = []
    if not isinstance(dels, dict):
        return rows
    for row in dels.values():
        if not isinstance(row, dict):
            continue
        if worker_id and str(row.get("worker_id")) != worker_id:
            continue
        if deliverable_type and str(row.get("type")) != deliverable_type:
            continue
        if task_id and str(row.get("task_id")) != task_id:
            continue
        if project_id and str(row.get("project_id") or "") != project_id:
            continue
        if status and str(row.get("status") or "") != status:
            continue
        if provider:
            pctx = row.get("provider_context") or {}
            if not isinstance(pctx, dict) or provider.lower() not in str(pctx).lower():
                continue
        created = str(row.get("created_at") or "")
        if date_from and created < date_from:
            continue
        if date_to and created > date_to:
            continue
        if q:
            blob = (
                f"{row.get('title')} {row.get('summary')} {row.get('type')} "
                f"{row.get('content', '')[:500]}"
            ).lower()
            if q not in blob and not any(tok in blob for tok in q.split() if len(tok) > 3):
                continue
        rows.append(row)
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows[: max(1, min(int(limit), 48))]


def create_continuation(
    *,
    worker_id: str,
    source_task_id: str,
    reason: str = "follow_up_request",
    continuation_state: dict[str, Any] | None = None,
    source_deliverable_id: str | None = None,
    continuation_prompt: str | None = None,
    status: str = "queued",
) -> str:
    st = load_runtime_state()
    ensure_worker_intel_schema(st)
    cid = f"cont_{uuid.uuid4().hex[:12]}"
    conts = st.setdefault("worker_continuations", {})
    if isinstance(conts, dict):
        conts[cid] = {
            "continuation_id": cid,
            "source_task_id": source_task_id,
            "source_deliverable_id": source_deliverable_id,
            "worker_id": worker_id,
            "reason": reason,
            "continuation_prompt": (continuation_prompt or reason)[:500],
            "status": status,
            "continuation_state": dict(continuation_state or {}),
            "created_at": utc_now_iso(),
        }
        cap = get_worker_memory_limits()["continuation"]
        if len(conts) > cap:
            oldest = sorted(conts.items(), key=lambda kv: str((kv[1] or {}).get("created_at") or ""))[:8]
            for k, _ in oldest:
                conts.pop(k, None)
    save_runtime_state(st)
    return cid


def set_session_active_worker(chat_key: str, worker_id: str) -> None:
    st = load_runtime_state()
    ensure_worker_intel_schema(st)
    ctx = st.setdefault("worker_session_context", {})
    if isinstance(ctx, dict):
        ctx[chat_key] = {"worker_id": worker_id, "at": utc_now_iso()}
    save_runtime_state(st)


def get_session_active_worker(chat_key: str) -> str | None:
    st = load_runtime_state()
    ctx = st.get("worker_session_context") or {}
    if isinstance(ctx, dict):
        row = ctx.get(chat_key)
        if isinstance(row, dict):
            return str(row.get("worker_id") or "") or None
    return None


def recover_worker_continuity() -> int:
    """Re-link interrupted tasks after runtime restart."""
    st = load_runtime_state()
    n = 0
    for tid, task in (st.get("task_registry") or {}).items():
        if not isinstance(task, dict):
            continue
        if str(task.get("state")) in ("running", "busy", "retrying"):
            wid = str(task.get("assigned_agent_id") or "")
            if wid:
                create_continuation(
                    worker_id=wid,
                    source_task_id=str(tid),
                    reason="runtime_restart_recovery",
                    continuation_state={"recovered": True},
                )
                n += 1
    return n


def build_workspace_awareness_snippet() -> dict[str, Any]:
    from app.services.operator_context import build_operator_context_panel

    op = build_operator_context_panel()
    repairs = op.get("latest_repair_contexts") or {}
    return {
        "project_count": len((op.get("project_registry") or {}).get("projects") or {})
        if isinstance(op.get("project_registry"), dict)
        else 0,
        "provider_ids": (op.get("provider_ids") or [])[:8],
        "repair_tracked": len(repairs) if isinstance(repairs, dict) else 0,
        "at": utc_now_iso(),
    }


def _memory_bucket(st: dict[str, Any], worker_id: str) -> dict[str, Any]:
    ensure_worker_intel_schema(st)
    wm = st.setdefault("worker_memory", {})
    if not isinstance(wm, dict):
        wm = {}
        st["worker_memory"] = wm
    mem = wm.get(worker_id)
    if not isinstance(mem, dict):
        mem = {
            "worker_id": worker_id,
            "recent_tasks": [],
            "recent_outputs": [],
            "recent_artifacts": [],
            "recent_failures": [],
            "deployment_history": [],
            "repair_history": [],
            "provider_actions": [],
            "workspace_context": [],
            "memory_summary": "",
        }
        wm[worker_id] = mem
    return mem


def _push_bounded(lst: Any, item: Any, cap: int) -> list[Any]:
    out = list(lst) if isinstance(lst, list) else []
    out.append(item)
    return out[-cap:]


def _summarize_memory(mem: dict[str, Any]) -> str:
    tasks = len(mem.get("recent_tasks") or [])
    outs = len(mem.get("recent_outputs") or [])
    fails = len(mem.get("recent_failures") or [])
    return f"{tasks} recent task(s), {outs} output(s), {fails} failure(s) tracked."


def _trim_deliverables(dels: dict[str, Any]) -> None:
    cap = get_worker_memory_limits()["deliverable"]
    if len(dels) <= cap:
        return
    ordered = sorted(dels.items(), key=lambda kv: str((kv[1] or {}).get("created_at") or ""))
    for k, _ in ordered[: len(dels) - cap]:
        dels.pop(k, None)

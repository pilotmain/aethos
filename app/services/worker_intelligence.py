# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime worker intelligence summaries, follow-ups, and effectiveness (Phase 3 Step 7)."""

from __future__ import annotations

import re
from typing import Any

from app.runtime.agent_work_state import find_runtime_agent_by_handle, get_output, normalize_handle
from app.runtime.worker_operational_memory import (
    build_worker_memory,
    get_session_active_worker,
    list_deliverables_for_worker,
    search_deliverables,
    set_session_active_worker,
)
from app.services.agent.activity_tracker import get_activity_tracker

_RE_FOLLOWUP_FIND = re.compile(
    r"(?is)^(?:what\s+did\s+you\s+find|what\s+did\s+we\s+find|show\s+(?:me\s+)?(?:the\s+)?last\s+result|show\s+last\s+output|show\s+(?:me\s+)?more|expand\s+(?:the\s+)?last\s+result|summarize\s+(?:the\s+)?research)\s*\??\s*$"
)
_RE_FOLLOWUP_CONTINUE = re.compile(
    r"(?is)^(?:continue|resume|pick\s+up)\s+(?:the\s+)?(.+?)\s*\??\s*$"
)
_RE_DELIVERABLE_SEARCH = re.compile(
    r"(?is)^show\s+(?:(?:latest|recent)\s+)?(?:deliverables?|outputs?)(?:\s+from\s+@?([\w-]+))?\s*\??\s*$"
)
_RE_TYPE_SEARCH = re.compile(
    r"(?is)^show\s+(deployment\s+reports?|repair\s+summaries?|market\s+research\s+outputs?|verification\s+reports?)\s*\??\s*$"
)

_TYPE_MAP = {
    "deployment reports": "deployment_report",
    "deployment report": "deployment_report",
    "repair summaries": "repair_summary",
    "repair summary": "repair_summary",
    "market research outputs": "research_summary",
    "market research output": "research_summary",
    "verification reports": "verification_report",
}


def build_worker_operational_summary(worker_id: str, runtime_row: dict[str, Any] | None = None) -> dict[str, Any]:
    mem = build_worker_memory(worker_id)
    reg_id = str((runtime_row or {}).get("registry_agent_id") or "")
    stats = get_activity_tracker().get_agent_statistics(reg_id) if reg_id else {}
    dels = list_deliverables_for_worker(worker_id, limit=6)
    role = (runtime_row or {}).get("role") or "worker"
    return {
        "worker_id": worker_id,
        "handle": (runtime_row or {}).get("handle"),
        "specialization": role,
        "recent_outcomes": [d.get("summary") for d in dels[:4]],
        "recent_failures": list(mem.get("recent_failures") or [])[-3:],
        "success_rate": stats.get("success_rate"),
        "total_actions": stats.get("total_actions"),
        "active_domains": [role],
        "memory_summary": mem.get("memory_summary"),
        "deliverable_count": len(list_deliverables_for_worker(worker_id, limit=99)),
    }


def build_worker_effectiveness(worker_id: str) -> dict[str, Any]:
    summary = build_worker_operational_summary(worker_id)
    rate = summary.get("success_rate")
    conf = "high" if rate is None or rate >= 75 else "medium" if rate >= 50 else "low"
    return {
        "worker_id": worker_id,
        "reliability": conf,
        "success_rate": rate,
        "deliverable_count": summary.get("deliverable_count"),
        "repair_effectiveness": "tracked" if summary.get("recent_failures") else "stable",
    }


def resolve_worker_followup(
    text: str,
    *,
    chat_key: str,
    handle: str | None = None,
) -> str | None:
    t = (text or "").strip()
    if not t:
        return None

    m_type = _RE_TYPE_SEARCH.match(t)
    if m_type:
        label = m_type.group(1).lower()
        dtype = _TYPE_MAP.get(label, "general_output")
        rows = search_deliverables(deliverable_type=dtype, limit=6)
        return _format_deliverable_list(rows, title=label)

    m_del = _RE_DELIVERABLE_SEARCH.match(t)
    if m_del:
        h = m_del.group(1)
        rows = search_deliverables(handle=h, limit=8) if h else search_deliverables(limit=8)
        return _format_deliverable_list(rows, title="latest deliverables")

    worker_id: str | None = None
    if handle:
        rt = find_runtime_agent_by_handle(handle)
        worker_id = str(rt.get("agent_id")) if rt else None
    if not worker_id:
        worker_id = get_session_active_worker(chat_key)

    if _RE_FOLLOWUP_FIND.match(t) and worker_id:
        return _format_latest_for_worker(worker_id)

    m_cont = _RE_FOLLOWUP_CONTINUE.match(t)
    if m_cont and worker_id:
        topic = m_cont.group(1)
        latest = list_deliverables_for_worker(worker_id, limit=1)
        if latest:
            d = latest[0]
            wh = _handle_for_worker(worker_id).lstrip("@")
            return (
                f"Continuing **{topic}** from prior work.\n\n"
                f"Last deliverable ({d.get('type')}): {d.get('summary')}\n\n"
                f"Mention: `@{wh} continue {topic}`"
            )
    return None


def _handle_for_worker(worker_id: str) -> str:
    from app.runtime.runtime_agents import list_runtime_agents

    row = (list_runtime_agents(include_expired=True)).get(worker_id) or {}
    h = str(row.get("handle") or "agent").lstrip("@")
    return h


def _format_latest_for_worker(worker_id: str) -> str:
    rt = None
    from app.runtime.runtime_agents import list_runtime_agents

    row = list_runtime_agents(include_expired=True).get(worker_id)
    if isinstance(row, dict):
        rt = row
    h = str(row.get("handle") or f"@{worker_id}") if row else f"worker {worker_id}"
    dels = list_deliverables_for_worker(worker_id, limit=1)
    if dels:
        d = dels[0]
        body = (d.get("content") or d.get("summary") or "")[:2000]
        return f"Latest from {h} ({d.get('type')}):\n\n{body}"
    oid = (row or {}).get("latest_output_id")
    if oid:
        out = get_output(str(oid))
        if out:
            return f"Latest output from {h}:\n\n{(out.get('content') or out.get('summary') or '')[:2000]}"
    return f"{h} has no completed deliverables yet. Assign work with `{h} <request>`."




def _format_deliverable_list(rows: list[dict[str, Any]], *, title: str) -> str:
    if not rows:
        return f"No {title} found in operational memory."
    lines = [f"**{title.title()}** ({len(rows)}):", ""]
    for r in rows:
        lines.append(f"• {r.get('type')} — {r.get('summary', '')[:120]} ({r.get('created_at', '')[:19]})")
    return "\n".join(lines)


def build_worker_intelligence_truth() -> dict[str, Any]:
    from app.runtime.runtime_agents import list_runtime_agents

    workers: list[dict[str, Any]] = []
    effectiveness: dict[str, Any] = {}
    for aid, row in list_runtime_agents(include_expired=True).items():
        if not isinstance(row, dict) or row.get("system"):
            continue
        summ = build_worker_operational_summary(str(aid), row)
        workers.append(summ)
        effectiveness[str(aid)] = build_worker_effectiveness(str(aid))
    return {
        "worker_memory": {w["worker_id"]: build_worker_memory(w["worker_id"]) for w in workers[:32]},
        "worker_deliverables": _recent_deliverables_slice(limit=24),
        "worker_continuations": _continuations_slice(limit=16),
        "worker_effectiveness": effectiveness,
        "worker_summaries": workers,
    }


def _recent_deliverables_slice(*, limit: int) -> list[dict[str, Any]]:
    from app.runtime.runtime_state import load_runtime_state

    st = load_runtime_state()
    dels = st.get("worker_deliverables") or {}
    rows = [r for r in dels.values() if isinstance(r, dict)] if isinstance(dels, dict) else []
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows[:limit]


def _continuations_slice(*, limit: int) -> list[dict[str, Any]]:
    from app.runtime.runtime_state import load_runtime_state

    st = load_runtime_state()
    c = st.get("worker_continuations") or {}
    rows = [r for r in c.values() if isinstance(r, dict)] if isinstance(c, dict) else []
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows[:limit]

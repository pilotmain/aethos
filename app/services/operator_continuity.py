# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator continuity — resume complex operational work from runtime truth (Phase 3 Step 9)."""

from __future__ import annotations

import re
from typing import Any

from app.runtime.worker_operational_memory import (
    get_session_active_worker,
    list_deliverables_for_worker,
    search_deliverables,
)
from app.runtime.workspace_operational_memory import (
    get_operator_continuity,
    list_research_chains,
    list_workspace_governance_events,
    set_operator_continuity,
)
from app.services.research_continuity import resolve_research_followup

_RE_RESUME = re.compile(
    r"(?is)^(?:continue\s+where\s+we\s+left\s+off|resume\s+(?:the\s+)?(?:repair|deployment|research)\s+flow)\s*\??\s*$"
)
_RE_LATEST_INVESTIGATION = re.compile(
    r"(?is)^show\s+(?:the\s+)?latest\s+(deployment\s+investigation|repair\s+investigation)\s*\??\s*$"
)
_RE_CONTINUE_ANALYSIS = re.compile(r"(?is)^continue\s+(?:the\s+)?competitor\s+analysis\s*\??\s*$")


def resolve_operator_continuity(text: str, *, chat_key: str) -> tuple[str | None, str]:
    t = (text or "").strip()
    if not t:
        return None, "none"

    research = resolve_research_followup(t, chat_key=chat_key, worker_id=get_session_active_worker(chat_key))
    if research:
        return research, "research_continuity"

    if _RE_RESUME.match(t):
        scope = _build_continuity_scope(chat_key)
        set_operator_continuity(chat_key, scope=scope)
        return _format_continuity_resume(scope), "operator_resume"

    if _RE_LATEST_INVESTIGATION.match(t):
        kind = "deployment" if "deployment" in t.lower() else "repair"
        dtype = "deployment_report" if kind == "deployment" else "repair_summary"
        rows = search_deliverables(deliverable_type=dtype, limit=1)
        if rows:
            return f"Latest {kind} investigation:\n\n{rows[0].get('summary')}\n\n{rows[0].get('content', '')[:2000]}", "latest_investigation"

    if _RE_CONTINUE_ANALYSIS.match(t):
        chains = list_research_chains(limit=1)
        if chains:
            c = chains[0]
            return (
                f"Resuming competitor analysis chain **{c.get('topic')}** "
                f"({len(c.get('related_deliverables') or [])} deliverable(s))."
            ), "research_chain"

    saved = get_operator_continuity(chat_key)
    if saved and "left off" in t.lower():
        return _format_continuity_resume(saved), "saved_continuity"

    return None, "none"


def build_operator_continuity_truth() -> dict[str, Any]:
    from app.runtime.runtime_state import load_runtime_state

    st = load_runtime_state()
    cont = st.get("operator_continuity") or {}
    chains = list_research_chains(limit=12)
    events = list_workspace_governance_events(limit=16)
    return {
        "scopes": dict(cont) if isinstance(cont, dict) else {},
        "research_chains": chains,
        "recent_governance": events,
    }


def _build_continuity_scope(chat_key: str) -> dict[str, Any]:
    worker_id = get_session_active_worker(chat_key)
    latest: dict[str, Any] | None = None
    if worker_id:
        dels = list_deliverables_for_worker(worker_id, limit=1)
        latest = dels[0] if dels else None
    deploy = search_deliverables(deliverable_type="deployment_report", limit=1)
    repair = search_deliverables(deliverable_type="repair_summary", limit=1)
    return {
        "chat_key": chat_key,
        "worker_id": worker_id,
        "latest_deliverable_id": (latest or {}).get("deliverable_id"),
        "latest_deployment_id": (deploy[0] if deploy else {}).get("deliverable_id"),
        "latest_repair_id": (repair[0] if repair else {}).get("deliverable_id"),
        "research_chains": [c.get("research_chain_id") for c in list_research_chains(limit=3)],
    }


def _format_continuity_resume(scope: dict[str, Any]) -> str:
    lines = ["**Continuing where you left off:**", ""]
    if scope.get("latest_deliverable_id"):
        lines.append(f"• Latest deliverable: `{scope['latest_deliverable_id']}`")
    if scope.get("latest_deployment_id"):
        lines.append(f"• Latest deployment investigation: `{scope['latest_deployment_id']}`")
    if scope.get("latest_repair_id"):
        lines.append(f"• Latest repair flow: `{scope['latest_repair_id']}`")
    if scope.get("research_chains"):
        lines.append(f"• Research chains: {', '.join(str(x) for x in scope['research_chains'][:3])}")
    lines.append("")
    lines.append("Ask to expand, compare, or export any of the above.")
    return "\n".join(lines)

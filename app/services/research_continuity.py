# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Research continuity: chains, comparisons, NL resume (Phase 3 Step 9)."""

from __future__ import annotations

import re
from typing import Any

from app.runtime.worker_operational_memory import get_deliverable, list_deliverables_for_worker, search_deliverables
from app.runtime.workspace_operational_memory import (
    add_deliverable_relationship,
    create_research_chain,
    get_research_chain,
    link_deliverable_to_chain,
    list_research_chains,
    record_workspace_governance_event,
    relationships_for_deliverable,
)

_RE_CONTINUE_RESEARCH = re.compile(
    r"(?is)^(?:continue|resume|update)\s+(?:the\s+)?(?:market\s+research|competitor\s+analysis|research)\s*\??\s*$"
)
_RE_COMPARE_PREVIOUS = re.compile(
    r"(?is)^compare\s+(?:with|to)\s+(?:previous|prior)\s+(?:findings|results?)\s*\??\s*$"
)
_RE_CHANGES_SINCE = re.compile(r"(?is)^what\s+changed\s+since\s+(yesterday|last\s+time)\s*\??\s*$")
_RE_EXPAND_DEPLOY = re.compile(r"(?is)^expand\s+(?:the\s+)?deployment\s+analysis\s*\??\s*$")


def ensure_research_deliverable_linked(
    *,
    deliverable_id: str,
    project_id: str | None = None,
    worker_id: str | None = None,
    topic: str = "research",
    prior_deliverable_id: str | None = None,
) -> str | None:
    """Attach deliverable to a research chain; optionally link to prior deliverable."""
    chains = list_research_chains(project_id=project_id, limit=1)
    chain_id = chains[0]["research_chain_id"] if chains else create_research_chain(
        project_id=project_id, topic=topic, worker_id=worker_id
    )
    link_deliverable_to_chain(chain_id, deliverable_id)
    if prior_deliverable_id:
        add_deliverable_relationship(
            from_id=deliverable_id,
            to_id=prior_deliverable_id,
            relationship="continuation_of",
        )
        record_workspace_governance_event(
            "research_continued",
            what=f"Linked {deliverable_id} after {prior_deliverable_id}",
            project_id=project_id,
            deliverable_id=deliverable_id,
            worker_id=worker_id,
        )
    return chain_id


def compare_deliverables(id_a: str, id_b: str) -> dict[str, Any]:
    a = get_deliverable(id_a)
    b = get_deliverable(id_b)
    if not a or not b:
        return {"ok": False, "error": "not_found"}
    add_deliverable_relationship(from_id=id_a, to_id=id_b, relationship="related_to", metadata={"compare": True})
    record_workspace_governance_event("deliverable_compared", what=f"{id_a} vs {id_b}")
    return {
        "ok": True,
        "a": {"id": id_a, "summary": a.get("summary"), "created_at": a.get("created_at")},
        "b": {"id": id_b, "summary": b.get("summary"), "created_at": b.get("created_at")},
        "diff_hint": _diff_summaries(str(a.get("summary") or ""), str(b.get("summary") or "")),
    }


def build_research_chain_view(chain_id: str) -> dict[str, Any]:
    chain = get_research_chain(chain_id)
    if not chain:
        return {"found": False, "research_chain_id": chain_id}
    dels = []
    for did in chain.get("related_deliverables") or []:
        row = get_deliverable(str(did))
        if row:
            dels.append(row)
    return {"found": True, "chain": chain, "deliverables": dels, "relationships": _chain_relationships(dels)}


def resolve_research_followup(text: str, *, chat_key: str, worker_id: str | None = None) -> str | None:
    t = (text or "").strip()
    if not t or not worker_id:
        return None
    if _RE_CONTINUE_RESEARCH.match(t):
        latest = list_deliverables_for_worker(worker_id, limit=1)
        if latest:
            d = latest[0]
            return (
                f"Continuing research from **{d.get('type')}**.\n\n"
                f"Last summary: {d.get('summary')}\n\n"
                f"Say what to update or expand."
            )
    if _RE_COMPARE_PREVIOUS.match(t):
        dels = list_deliverables_for_worker(worker_id, limit=2)
        if len(dels) >= 2:
            cmp = compare_deliverables(str(dels[0]["deliverable_id"]), str(dels[1]["deliverable_id"]))
            if cmp.get("ok"):
                return f"**Latest:** {cmp['a']['summary']}\n\n**Previous:** {cmp['b']['summary']}\n\n{cmp.get('diff_hint', '')}"
    if _RE_CHANGES_SINCE.match(t):
        rows = search_deliverables(worker_id=worker_id, deliverable_type="research_summary", limit=2)
        if len(rows) >= 2:
            return (
                f"Since last research:\n\n"
                f"• Now: {rows[0].get('summary')}\n"
                f"• Before: {rows[1].get('summary')}"
            )
    if _RE_EXPAND_DEPLOY.match(t):
        rows = search_deliverables(worker_id=worker_id, deliverable_type="deployment_report", limit=1)
        if rows:
            return f"Latest deployment analysis:\n\n{rows[0].get('summary')}\n\n{rows[0].get('content', '')[:1500]}"
    return None


def _chain_relationships(dels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in dels:
        did = str(d.get("deliverable_id") or "")
        out.extend(relationships_for_deliverable(did))
    return out[:32]


def build_deliverable_relationships_view(*, limit: int = 32) -> list[dict[str, Any]]:
    from app.runtime.runtime_state import load_runtime_state

    st = load_runtime_state()
    rels = st.get("deliverable_relationships") or {}
    rows = [r for r in rels.values() if isinstance(r, dict)] if isinstance(rels, dict) else []
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows[: max(1, min(int(limit), 64))]


def _diff_summaries(a: str, b: str) -> str:
    if a == b:
        return "Summaries match."
    return "Summaries differ — review both deliverables for detail."

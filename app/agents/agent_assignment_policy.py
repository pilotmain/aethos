# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Deterministic coordination-agent selection (OpenClaw reliability — Step 1).

Priority (stable sort):
1. coordination_health (healthy before degraded; recovering/failed/offline/overloaded excluded)
2. matching agent_type
3. least active_tasks
4. lowest retry burden (retrying/recovering tasks weighted higher)
5. oldest idle / tie-break: earliest created_at, then agent_id
"""

from __future__ import annotations

from typing import Any

from app.agents.agent_coordination import assign_task_to_agent, detach_task_from_coordination_agent
from app.agents.agent_health import (
    effective_coordination_health,
    is_assignable_coordination_health,
)
from app.agents.agent_registry import get_agent, list_agents_for_user
from app.orchestration import task_registry
from app.runtime.runtime_state import utc_now_iso

POLICY_VERSION = "coordination_v1"


def _retry_burden(st: dict[str, Any], active_task_ids: list[Any]) -> int:
    burden = 0
    for ref in active_task_ids:
        tid = str(ref)
        if not tid:
            continue
        t = task_registry.get_task(st, tid)
        if not isinstance(t, dict):
            burden += 1
            continue
        stt = str(t.get("state") or "")
        if stt in ("retrying", "recovering"):
            burden += 4
        elif stt in ("running", "waiting"):
            burden += 2
        else:
            burden += 1
    return burden


def _health_sort_rank(health: str) -> int:
    h = str(health or "").lower()
    if h == "healthy":
        return 0
    if h == "degraded":
        return 1
    return 9


def rank_coordination_agents_for_task(
    st: dict[str, Any],
    *,
    user_id: str,
    agent_type: str,
    exclude_agent_ids: set[str] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(agent_id, rationale_row)`` best-first."""
    uid = str(user_id or "").strip()
    want_type = str(agent_type or "operator").strip().lower() or "operator"
    ex = {str(x) for x in (exclude_agent_ids or set()) if str(x)}
    ranked: list[tuple[str, dict[str, Any], tuple[Any, ...]]] = []
    for row in list_agents_for_user(st, uid):
        if not isinstance(row, dict):
            continue
        aid = str(row.get("agent_id") or "")
        if not aid or aid in ex:
            continue
        ch = effective_coordination_health(row)
        if not is_assignable_coordination_health(ch):
            continue
        at = str(row.get("agent_type") or "operator").strip().lower() or "operator"
        if at != want_type:
            continue
        active = list(row.get("active_tasks") or [])
        burden = _retry_burden(st, active)
        created = str(row.get("created_at") or "")
        # Lower tuple is better: health rank, active count, burden, older created_at, agent_id
        key = (_health_sort_rank(ch), len(active), burden, created, aid)
        rationale = {
            "agent_id": aid,
            "coordination_health": ch,
            "agent_type": at,
            "active_tasks": len(active),
            "retry_burden": burden,
            "sort_key": key,
        }
        ranked.append((aid, rationale, key))
    ranked.sort(key=lambda x: (x[2][0], x[2][1], x[2][2], x[2][3], x[2][4]))
    return [(aid, r) for aid, r, _k in ranked]


def select_coordination_agent_for_task(
    st: dict[str, Any],
    *,
    user_id: str,
    agent_type: str = "operator",
    exclude_agent_ids: set[str] | None = None,
) -> tuple[str | None, dict[str, Any]]:
    ranked = rank_coordination_agents_for_task(st, user_id=user_id, agent_type=agent_type, exclude_agent_ids=exclude_agent_ids)
    if not ranked:
        return None, {
            "policy_version": POLICY_VERSION,
            "ranked_candidates": [],
            "reason": "no_eligible_agent",
        }
    best_id, best_r = ranked[0]
    return best_id, {
        "policy_version": POLICY_VERSION,
        "selected": best_r,
        "ranked_candidates": [r for _aid, r in ranked[:8]],
    }


def assign_task_with_coordination_policy(
    st: dict[str, Any],
    task_id: str,
    *,
    user_id: str,
    agent_type: str = "operator",
    preferred_agent_id: str | None = None,
    exclude_agent_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Assign ``task_id`` using policy + persist ``coordination_assignment`` on the task."""
    tid = str(task_id)
    t = task_registry.get_task(st, tid)
    if not t:
        return {"ok": False, "reason": "task_not_found"}
    uid = str(user_id or "").strip()
    ex = set(exclude_agent_ids or set())
    chosen: str | None = None
    meta: dict[str, Any] = {}
    if preferred_agent_id:
        pa = str(preferred_agent_id)
        row = get_agent(st, pa)
        if isinstance(row, dict) and str(row.get("user_id") or "").strip() == uid:
            ch = effective_coordination_health(row)
            at = str(row.get("agent_type") or "operator").strip().lower() or "operator"
            if (
                pa not in ex
                and is_assignable_coordination_health(ch)
                and at == str(agent_type or "operator").strip().lower()
            ):
                chosen = pa
                meta = {
                    "policy_version": POLICY_VERSION,
                    "mode": "preferred",
                    "selected": {"agent_id": pa, "coordination_health": ch, "agent_type": at},
                    "ranked_candidates": [],
                }
    if not chosen:
        chosen, meta = select_coordination_agent_for_task(
            st, user_id=uid, agent_type=agent_type, exclude_agent_ids=ex
        )
        if chosen:
            meta["mode"] = "policy"
    if not chosen:
        return {"ok": False, **meta}
    ts = utc_now_iso()
    assignment = {
        "agent_id": chosen,
        "policy_version": POLICY_VERSION,
        "assigned_at": ts,
        "rationale": meta,
    }
    assign_task_to_agent(st, chosen, tid, coordination_assignment=assignment)
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["coordination_policy_assignments_total"] = int(m.get("coordination_policy_assignments_total") or 0) + 1
    return {"ok": True, "agent_id": chosen, "coordination_assignment": assignment}


def reassign_tasks_from_unhealthy_coordination_agent(
    st: dict[str, Any],
    unhealthy_agent_id: str,
    *,
    reason: str,
) -> dict[str, Any]:
    """Detach active tasks from an unhealthy agent and re-assign via policy (excluding that agent)."""
    aid = str(unhealthy_agent_id)
    row = get_agent(st, aid)
    if not isinstance(row, dict):
        return {"reassigned": 0, "detached": 0, "failures": 0}
    active = [str(x) for x in (row.get("active_tasks") or []) if str(x)]
    ex = {aid}
    reassigned = detached = failures = 0
    uid = str(row.get("user_id") or "")
    at_default = str(row.get("agent_type") or "operator")
    for tid in list(active):
        detach_task_from_coordination_agent(st, tid)
        detached += 1
        t2 = task_registry.get_task(st, tid)
        if not isinstance(t2, dict):
            failures += 1
            continue
        uid2 = str(t2.get("user_id") or uid)
        res = assign_task_with_coordination_policy(
            st,
            tid,
            user_id=uid2,
            agent_type=at_default,
            exclude_agent_ids=ex,
        )
        if res.get("ok"):
            reassigned += 1
        else:
            failures += 1
            task_registry.update_task_state(
                st,
                tid,
                str(t2.get("state") or "queued"),
                coordination_assignment={
                    "policy_version": POLICY_VERSION,
                    "pending_reassign": True,
                    "reason": res.get("reason") or "no_eligible_agent",
                    "source_agent": aid,
                    "trigger": reason,
                },
            )
    from app.agents import agent_events

    agent_events.emit_agent_event(
        st,
        "coordination_agent_tasks_reassigned",
        agent_id=aid,
        user_id=uid,
        reassigned=reassigned,
        detached=detached,
        failures=failures,
        reason=str(reason)[:200],
    )
    return {"reassigned": reassigned, "detached": detached, "failures": failures}

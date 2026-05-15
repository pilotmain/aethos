"""Cross-cutting validation of ``aethos.json`` orchestration + execution + sessions."""

from __future__ import annotations

from typing import Any

from app.execution import execution_dependencies
from app.execution import execution_plan
from app.orchestration import task_queue
from app.orchestration import task_registry


def validate_runtime_state(st: dict[str, Any]) -> dict[str, Any]:
    """
    Return ``{ok, issues, issue_count}`` — read-only unless caller mutates via cleanup.

    Covers: queue membership, plan/task linkage, session ownership, DAG validity,
    checkpoint/plan alignment, execution memory keys, retry shape hints.
    """
    issues: list[str] = []
    tr = task_registry.registry(st)
    if not isinstance(tr, dict):
        return {"ok": False, "issues": ["task_registry_not_dict"], "issue_count": 1}

    # --- Queues: entries must reference existing tasks ---
    for qn in task_queue.QUEUE_NAMES:
        q = st.get(qn)
        if not isinstance(q, list):
            issues.append(f"queue_not_list:{qn}")
            continue
        for ref in q:
            tid = str(ref)
            if tid and tid not in tr:
                issues.append(f"queue_orphan_ref:{qn}:{tid}")

    # --- Tasks: owner session must exist when set ---
    rs = st.get("runtime_sessions")
    rs_map = rs if isinstance(rs, dict) else {}
    for tid, t in tr.items():
        if not isinstance(t, dict):
            continue
        sid = t.get("owner_session_id")
        if sid and str(sid) not in rs_map:
            issues.append(f"task_orphan_session:{tid}:{sid}")

    # --- Sessions: active_tasks should exist in registry (soft: warn only if missing) ---
    for sid, row in rs_map.items():
        if not isinstance(row, dict):
            continue
        for at in row.get("active_tasks") or []:
            aid = str(at)
            if aid and aid not in tr:
                issues.append(f"session_stale_task_ref:{sid}:{aid}")

    # --- Plans: task_id exists; DAG valid ---
    ex = execution_plan.execution_root(st)
    plans = ex.get("plans") or {}
    if not isinstance(plans, dict):
        issues.append("execution.plans_not_dict")
    else:
        for pid, plan in plans.items():
            if not isinstance(plan, dict):
                issues.append(f"plan_invalid:{pid}")
                continue
            tid = str(plan.get("task_id") or "")
            if tid and tid not in tr:
                issues.append(f"plan_orphan_task:{pid}:{tid}")
            if not execution_dependencies.validate_plan_dependency_dag(plan):
                issues.append(f"plan_invalid_dag:{pid}")
            for s in plan.get("steps") or []:
                if not isinstance(s, dict):
                    continue
                for dep in s.get("depends_on") or []:
                    d = str(dep)
                    ids = {str(x.get("step_id")) for x in plan.get("steps") or [] if isinstance(x, dict)}
                    if d and d not in ids:
                        issues.append(f"plan_bad_dep:{pid}:{s.get('step_id')}->{d}")
                if (
                    str(s.get("status") or "") == "retrying"
                    and int(s.get("retry_count") or 0) > 0
                    and s.get("next_retry_at") is None
                ):
                    issues.append(f"plan_retry_missing_next:{pid}:{s.get('step_id')}")

    # --- Checkpoints: plan keys exist ---
    cps = ex.get("checkpoints") or {}
    if isinstance(cps, dict) and isinstance(plans, dict):
        for pid in cps.keys():
            if pid not in plans:
                issues.append(f"checkpoint_orphan_plan:{pid}")

    # --- Execution memory bucket keys -> task ids ---
    mem = ex.get("memory") or {}
    if isinstance(mem, dict):
        for mk in mem.keys():
            if str(mk) not in tr:
                issues.append(f"memory_orphan_task:{mk}")

    ca = st.get("coordination_agents") or {}
    if isinstance(ca, dict):
        for aid, ag in ca.items():
            if not isinstance(ag, dict):
                issues.append(f"coordination_agent_invalid:{aid}")
                continue
            for atid in ag.get("active_tasks") or []:
                if str(atid) and str(atid) not in tr:
                    issues.append(f"agent_orphan_active_task:{aid}:{atid}")
            asid = ag.get("owner_session_id")
            if asid and str(asid) not in rs_map:
                issues.append(f"agent_orphan_session:{aid}:{asid}")

    ad = st.get("agent_delegations") or {}
    if isinstance(ad, dict):
        for did, dg in ad.items():
            if not isinstance(dg, dict):
                issues.append(f"delegation_invalid:{did}")
                continue
            tid = str(dg.get("task_id") or "")
            if tid and tid not in tr:
                issues.append(f"delegation_orphan_task:{did}:{tid}")
            pa = str(dg.get("parent_agent_id") or "")
            if pa and pa not in ca:
                issues.append(f"delegation_orphan_parent:{did}:{pa}")
            ca2 = str(dg.get("child_agent_id") or "")
            if ca2 and ca2 not in ca:
                issues.append(f"delegation_orphan_child:{did}:{ca2}")

    # --- Planning intelligence rows: task + plan refs must exist ---
    ex2 = execution_plan.execution_root(st)
    plans2 = ex2.get("plans") or {}
    if not isinstance(plans2, dict):
        plans2 = {}
    pr = st.get("planning_records")
    if isinstance(pr, dict):
        for plnid, prow in pr.items():
            if not isinstance(prow, dict):
                issues.append(f"planning_record_invalid:{plnid}")
                continue
            tid = str(prow.get("task_id") or "")
            if tid and tid not in tr:
                issues.append(f"planning_orphan_task:{plnid}:{tid}")
            pplan = str(prow.get("plan_id") or "")
            if pplan and pplan not in plans2:
                issues.append(f"planning_orphan_plan:{plnid}:{pplan}")

    return {"ok": len(issues) == 0, "issues": issues, "issue_count": len(issues)}

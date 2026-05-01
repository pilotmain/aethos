"""Current work summary + light artifact pointers for the Web UI (no dashboards)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.conversation_context import ConversationContext
from app.models.project_context import NexaWorkspaceProject
from app.services.document_generation import list_document_artifacts_for_user
from app.services.lightweight_workflow import _is_flow_expired, _load_flow, _pending_steps
from app.services.agent_job_service import AgentJobService


@dataclass
class FlowSummaryOut:
    has_flow: bool
    expired: bool
    goal: str | None
    total_steps: int
    completed_steps: int
    next_command: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _step_counts(st: dict[str, Any]) -> tuple[int, int]:
    steps = list(st.get("steps") or [])
    if not steps:
        return 0, 0
    total = len(steps)
    done = sum(1 for s in steps if str(s.get("status") or "") == "done")
    return done, total


def build_work_context(
    db: Session,
    cctx: ConversationContext,
    app_user_id: str,
) -> dict[str, Any]:
    """
    JSON-safe summary for /web/work-context: flow progress, project/agent lines, last few artifacts.
    """
    st = _load_flow(cctx.current_flow_state_json)
    now = datetime.now(timezone.utc)
    expired = bool(st) and _is_flow_expired(st, now=now)

    done_n, tot_n = (0, 0)
    next_cmd: str | None = None
    goal: str | None = None
    has_flow = bool(st) and not expired
    if st and not expired:
        g = str(st.get("goal") or "").strip()
        goal = g[:500] if g else None
        done_n, tot_n = _step_counts(st)
        pend = _pending_steps(st)
        if pend:
            next_cmd = (str(pend[0].get("command") or "").strip() or None)[:500]

    lines: list[str] = []
    apid = getattr(cctx, "active_project_id", None)
    if apid:
        row = db.get(NexaWorkspaceProject, int(apid))
        if row and row.owner_user_id == app_user_id:
            nm = (row.name or "").strip() or "Project"
            pp = (row.path_normalized or "").strip()
            pl = pp if len(pp) <= 160 else pp[:157] + "…"
            lines.append(f"Project: {nm[:120]}")
            lines.append(f"Working in: {pl}")
    elif cctx.active_project and (cctx.active_project or "").strip():
        lines.append(f"Project: {cctx.active_project[:120]}")
    ag = cctx.active_agent or cctx.last_agent_key
    if ag and str(ag).strip():
        lines.append(f"Agent: {str(ag)[:64]}")
    if st and not expired:
        g0 = (goal or "Current workflow")[:200]
        lines.insert(0, f"Current work: {g0}")
        if tot_n:
            lines.append(f"Completed: {done_n} of {tot_n}")
        if next_cmd:
            short = next_cmd if len(next_cmd) <= 100 else next_cmd[:97] + "…"
            lines.append(f"Next: {short}")
    elif st and expired:
        lines.append("Last workflow expired — start a new one from chat if you like.")
    if cctx.last_intent and (cctx.last_intent or "").strip():
        lines.append(f"Last intent: {cctx.last_intent[:64]}")

    # Recent documents + jobs (compact)
    art_list: list[dict[str, Any]] = []
    try:
        docs = list_document_artifacts_for_user(db, app_user_id, limit=4)
        for d in docs:
            art_list.append(
                {
                    "kind": "document",
                    "id": d.id,
                    "label": f"{(d.title or 'Document')[:64]} · {d.format.upper()}",
                }
            )
    except Exception:  # noqa: BLE001
        pass
    try:
        js = AgentJobService().list_jobs(db, app_user_id, limit=4)
        for j in js[:4]:
            art_list.append(
                {
                    "kind": "job",
                    "id": j.id,
                    "label": f"#{j.id} {j.status} — {(j.title or 'Job')[:80]}",
                }
            )
    except Exception:  # noqa: BLE001
        pass

    return {
        "flow": FlowSummaryOut(
            has_flow=has_flow,
            expired=bool(st and expired),
            goal=goal,
            total_steps=tot_n,
            completed_steps=done_n,
            next_command=next_cmd,
        ).to_dict(),
        "lines": [x for x in lines if (x or "").strip()],
        "recent_artifacts": art_list[:8],
    }

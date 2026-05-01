"""Deterministic post-approval summary for workers/UI (Phase 37).

Execution continues through the existing host worker + job locks; this payload is the
explicit resume record attached to gateway approval responses.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.gateway.context import GatewayContext


def resume_after_approval(
    db: Session,
    ctx: GatewayContext,
    job: Any,
    decision: str,
) -> dict[str, Any]:
    """
    Reload-oriented summary after a job transition triggered by user approval/deny.

    Host workers already poll ``agent_jobs``; duplicate execution is prevented via row locks.
    """
    _ = db
    jid = getattr(job, "id", None)
    st = getattr(job, "status", None)
    wt = getattr(job, "worker_type", None)
    return {
        "job_id": jid,
        "status": st,
        "worker_type": wt,
        "decision": decision,
        "channel": ctx.channel,
        "resume": {
            "kind": "host_worker_poll",
            "note": "Worker continues from persisted job status; no duplicate gateway mission.",
        },
    }


__all__ = ["resume_after_approval"]

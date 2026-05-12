# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persist approval wait state on agent jobs (Phase 38) — survives API restart."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_job import AgentJob
from app.services.gateway.context import GatewayContext


def approval_context_snapshot(
    ctx: GatewayContext | None,
    *,
    resume_kind: str = "host_worker_poll",
    original_action: str | None = None,
    risk: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serializable snapshot for ``approval_context_json`` (no secrets, no large payloads)."""
    snap: dict[str, Any] = {
        "resume_kind": resume_kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gateway_context": {},
    }
    if original_action:
        snap["original_action"] = str(original_action)[:2000]
    if risk:
        snap["risk"] = str(risk)[:128]
    if ctx is not None:
        snap["gateway_context"] = {
            "user_id": ctx.user_id,
            "channel": ctx.channel,
            "locale": ctx.locale,
            "permission_keys": sorted(ctx.permissions.keys()),
            "extras_keys": sorted(ctx.extras.keys()),
        }
    if extra:
        for k, v in extra.items():
            if k in snap:
                continue
            snap[k] = v
    return snap


def persist_job_waiting_approval(
    db: Session,
    job: Any,
    *,
    ctx: GatewayContext | None = None,
    resume_kind: str = "host_worker_poll",
    original_action: str | None = None,
    risk: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Mark job as awaiting approval and store gateway-safe resume metadata."""
    jid = getattr(job, "id", None)
    if jid is None:
        return
    row = db.get(AgentJob, int(jid))
    if row is None:
        return
    row.awaiting_approval = True
    row.approval_context_json = approval_context_snapshot(
        ctx,
        resume_kind=resume_kind,
        original_action=original_action,
        risk=risk,
        extra=extra,
    )
    db.add(row)
    db.commit()
    db.refresh(row)


def finalize_job_after_gateway_approval(
    db: Session,
    job: Any,
    approver_user_id: str,
    decision: str,
) -> None:
    """Clear wait flags after user decision; record who/when (Phase 38 resume complete)."""
    jid = getattr(job, "id", None)
    if jid is None:
        return
    row = db.get(AgentJob, int(jid))
    if row is None:
        return
    if row.user_id != approver_user_id:
        return
    row.awaiting_approval = False
    row.approval_context_json = None
    row.approval_decision = (decision or "")[:64] or None
    row.approved_at = datetime.utcnow()
    row.approved_by_user_id = approver_user_id
    db.add(row)
    db.commit()
    db.refresh(row)


__all__ = [
    "approval_context_snapshot",
    "persist_job_waiting_approval",
    "finalize_job_after_gateway_approval",
]

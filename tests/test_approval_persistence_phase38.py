"""Phase 38 — approval_context_json survives reload and finalize clears wait state."""

from __future__ import annotations

import pytest

from app.models.agent_job import AgentJob
from app.services.gateway.approval_persistence import (
    finalize_job_after_gateway_approval,
    persist_job_waiting_approval,
)
from app.services.gateway.context import GatewayContext


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_persist_then_reload_then_finalize(db_session) -> None:
    j = AgentJob(
        user_id="persist_u1",
        source="web",
        kind="dev_task",
        worker_type="dev_executor",
        title="t",
        instruction="",
        status="waiting_approval",
        approval_required=True,
        payload_json={},
    )
    db_session.add(j)
    db_session.commit()
    db_session.refresh(j)

    ctx = GatewayContext.from_channel("persist_u1", "web", {})
    persist_job_waiting_approval(
        db_session,
        j,
        ctx=ctx,
        resume_kind="host_worker_poll",
        original_action="unit_test",
    )
    db_session.refresh(j)
    assert j.awaiting_approval is True
    assert isinstance(j.approval_context_json, dict)
    assert j.approval_context_json.get("resume_kind") == "host_worker_poll"

    jid = j.id
    db_session.expunge_all()
    j2 = db_session.get(AgentJob, jid)
    assert j2 is not None
    assert j2.awaiting_approval is True
    assert (j2.approval_context_json or {}).get("gateway_context", {}).get("user_id") == "persist_u1"

    finalize_job_after_gateway_approval(db_session, j2, "persist_u1", "approve")
    db_session.refresh(j2)
    assert j2.awaiting_approval is False
    assert j2.approval_context_json is None
    assert j2.approval_decision == "approve"

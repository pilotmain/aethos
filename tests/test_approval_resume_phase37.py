# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 37 — explicit approval resume payload and ctx approval_state."""

from __future__ import annotations

import types

import pytest

from app.services.gateway.approval_flow import _merge_resume
from app.services.gateway.approval_resume import resume_after_approval
from app.services.gateway.context import GatewayContext


def test_resume_after_approval_returns_host_worker_resume_record(db_session) -> None:
    ctx = GatewayContext(user_id="u1", channel="telegram")
    job = types.SimpleNamespace(id=7, status="approved_to_run", worker_type="dev_executor")
    rec = resume_after_approval(db_session, ctx, job, "approve")
    assert rec["job_id"] == 7
    assert rec["status"] == "approved_to_run"
    assert rec["worker_type"] == "dev_executor"
    assert rec["decision"] == "approve"
    assert rec["channel"] == "telegram"
    assert rec["resume"]["kind"] == "host_worker_poll"


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_merge_resume_attaches_approval_resume_and_updates_ctx(db_session) -> None:
    ctx = GatewayContext(user_id="owner1", channel="web")
    job = types.SimpleNamespace(id=99, status="queued", worker_type="ops")
    payload: dict = {"mode": "chat", "text": "Job updated."}
    out = _merge_resume(payload, db_session, ctx, job, "deny")
    assert out["approval_resume"]["decision"] == "deny"
    assert out["approval_resume"]["job_id"] == 99
    assert ctx.approval_state == {"job_id": 99, "status": "queued", "decision": "deny"}

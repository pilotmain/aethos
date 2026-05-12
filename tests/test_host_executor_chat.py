# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Host executor chat path: confirm in context, enqueue job (no shell)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.models.agent_job import AgentJob
from app.models.conversation_context import ConversationContext
from app.services import next_action_apply as naa
from app.services.host_executor_chat import drain_host_executor_web_notifications


class _HostOn:
    nexa_host_executor_enabled = True
    nexa_access_permissions_enforced = False
    # other get_settings attrs: best-effort for in-memory sqlite
    host_executor_work_root = "/tmp"
    host_executor_timeout_seconds = 120
    host_executor_max_file_bytes = 262_144


@pytest.fixture
def in_memory_db() -> Session:
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    sm = sessionmaker(bind=e)()
    yield sm
    sm.close()


def test_chat_run_tests_then_yes_queues_job(in_memory_db: Session) -> None:
    db = in_memory_db
    cctx = ConversationContext(user_id="hx_u1", session_id="default", recent_messages_json="[]")
    db.add(cctx)
    db.commit()
    c2 = db.get(ConversationContext, cctx.id) or cctx

    with (
        patch("app.core.config.get_settings", return_value=_HostOn()),
        patch("app.services.permission_request_flow.get_settings", return_value=_HostOn()),
        patch("app.services.host_executor_chat.get_settings", return_value=_HostOn()),
        patch("app.services.next_action_apply.get_settings", return_value=_HostOn()),
    ):
        r1 = naa.apply_next_action_to_user_text(
            db, c2, "run tests", web_session_id="sess-a"
        )
    assert r1.early_assistant and "host executor" in r1.early_assistant.lower()
    assert "Approval: required" in (r1.early_assistant or "")
    db.refresh(c2)
    assert c2.next_action_pending_inject_json and "host_executor" in c2.next_action_pending_inject_json

    with (
        patch("app.core.config.get_settings", return_value=_HostOn()),
        patch("app.services.permission_request_flow.get_settings", return_value=_HostOn()),
        patch("app.services.host_executor_chat.get_settings", return_value=_HostOn()),
        patch("app.services.next_action_apply.get_settings", return_value=_HostOn()),
    ):
        r2 = naa.apply_next_action_to_user_text(db, c2, "yes", web_session_id="sess-a")
    assert r2.early_assistant and "Queued local action" in r2.early_assistant
    assert r2.related_job_ids and len(r2.related_job_ids) == 1

    job = db.query(AgentJob).filter(AgentJob.user_id == "hx_u1").order_by(AgentJob.id.desc()).first()
    assert job is not None
    assert job.status == "needs_approval"
    assert (job.command_type or "").lower() == "host-executor"
    pl = dict(job.payload_json or {})
    assert pl.get("host_action") == "run_command"
    assert pl.get("run_name") == "pytest"
    assert pl.get("chat_origin", {}).get("web_session_id") == "sess-a"
    assert r2.related_job_ids[0] == job.id


def test_drain_web_completion_once(in_memory_db: Session) -> None:
    db = in_memory_db
    from app.services.agent_job_service import AgentJobService
    from app.schemas.agent_job import AgentJobCreate

    svc = AgentJobService()
    j = svc.create_job(
        db,
        "hx_u2",
        AgentJobCreate(
            kind="local_action",
            worker_type="local_tool",
            title="t",
            instruction="i",
            command_type="host-executor",
            payload_json={
                "host_action": "git_status",
                "chat_origin": {"web_session_id": "ws1"},
                "chat_pending_title": "Git status",
                "web_chat_notified": False,
            },
            source="chat",
        ),
    )
    svc.repo.update(db, j, status="completed", result="ok-output")

    text1, ev1 = drain_host_executor_web_notifications(db, "hx_u2", "ws1")
    assert text1 and "ok-output" in text1 and "success" in text1.lower()
    assert text1 and "Job #" in text1
    assert ev1 and ev1[0]["kind"] == "local_action_muted"

    text2, ev2 = drain_host_executor_web_notifications(db, "hx_u2", "ws1")
    assert text2 is None and ev2 == []


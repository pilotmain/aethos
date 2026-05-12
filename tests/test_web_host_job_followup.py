# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic host job status lines in Web chat (no LLM)."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.db import SessionLocal, ensure_schema
from app.models.agent_job import AgentJob
from app.models.agent_team import AgentAssignment
from app.services.content_provenance import InstructionSource, apply_trusted_instruction_source
from app.services.nexa_safety_policy import stamp_host_payload
from app.services.web_host_job_followup import is_web_host_status_query, try_web_host_job_status_reply
from app.services.workspace_registry import add_root


def test_is_web_host_status_query() -> None:
    assert is_web_host_status_query("any update")
    assert is_web_host_status_query("any update.")
    assert is_web_host_status_query("status")
    assert is_web_host_status_query("report progress")
    assert is_web_host_status_query("report progress please")
    assert is_web_host_status_query("are you done?")
    assert is_web_host_status_query("what happened")
    assert not is_web_host_status_query("list files in /tmp")


@pytest.fixture
def followup_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    ensure_schema()
    db = SessionLocal()
    uid = f"whf_{uuid.uuid4().hex[:12]}"
    try:
        add_root(db, uid, root)
        yield db, root, uid
    finally:
        db.close()


def test_status_query_returns_session_scoped_job(
    followup_env: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only jobs with chat_origin.web_session_id == this session are returned."""
    db, root, uid = followup_env
    monkeypatch.chdir(root)
    pl = stamp_host_payload(
        apply_trusted_instruction_source(
            {
                "host_action": "list_directory",
                "relative_path": ".",
                "chat_origin": {
                    "web_session_id": "sess-a",
                    "permission_request_id": "9",
                },
            },
            InstructionSource.USER_MESSAGE.value,
        )
    )
    j1 = AgentJob(
        user_id=uid,
        source="chat",
        kind="local_action",
        worker_type="local_tool",
        title="List",
        instruction="x",
        command_type="host-executor",
        status="completed",
        approval_required=False,
        payload_json=pl,
        result="OUT_A",
    )
    j2 = AgentJob(
        user_id=uid,
        source="chat",
        kind="local_action",
        worker_type="local_tool",
        title="Other",
        instruction="x",
        command_type="host-executor",
        status="completed",
        approval_required=False,
        payload_json={
            "host_action": "list_directory",
            "relative_path": ".",
            "chat_origin": {"web_session_id": "other"},
        },
        result="OUT_B",
    )
    db.add(j1)
    db.add(j2)
    db.commit()
    r = try_web_host_job_status_reply(db, uid, "any update", web_session_id="sess-a")
    assert r is not None
    assert "OUT_A" in (r.reply or "")
    assert "OUT_B" not in (r.reply or "")


def test_status_empty_session_shows_friendly_copy_not_internals(followup_env: tuple) -> None:
    db, _root, uid = followup_env
    r = try_web_host_job_status_reply(db, uid, "report progress please", web_session_id="sess-a")
    assert r is not None
    assert "No active jobs are linked to this chat session" in (r.reply or "")
    assert "host executor" not in (r.reply or "").lower()
    assert "chat_origin" not in (r.reply or "")


def test_status_prefers_team_activity_without_session_host_jobs(followup_env: tuple) -> None:
    db, _root, uid = followup_env
    db.add(
        AgentAssignment(
            user_id=uid,
            organization_id=None,
            assigned_to_handle="research_analyst",
            assigned_by_handle="user",
            title="Market brief",
            description="test",
            status="completed",
            input_json={"user_message": "x"},
            channel="web",
            web_session_id="other-sess",
        )
    )
    db.commit()
    r = try_web_host_job_status_reply(db, uid, "any update", web_session_id="sess-a")
    assert r is not None
    assert "Team activity" in (r.reply or "")
    assert "research-analyst" in (r.reply or "").lower()

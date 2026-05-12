# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Cursor Cloud integration (Phase 1) — dispatch hook and client helpers."""

from __future__ import annotations

import logging
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.core.db import SessionLocal, ensure_schema
from app.models.audit_log import AuditLog
from app.models.user_agent import UserAgent
from app.services.agent_team.planner import classify_assignment_instruction_kind
from app.services.agent_team.service import create_assignment, dispatch_assignment
from app.services.cursor_integration.cursor_client import (
    CursorApiError,
    CursorCloudClient,
    parse_create_agent_response,
    parse_run_status,
    terminal_run_status,
)


def test_parse_create_agent_response_nested() -> None:
    agent_id, run_id, st = parse_create_agent_response(
        {
            "agent": {"id": "ag-1"},
            "run": {"id": "run-1", "status": "RUNNING"},
        }
    )
    assert agent_id == "ag-1"
    assert run_id == "run-1"
    assert st == "RUNNING"


def test_terminal_run_status() -> None:
    assert terminal_run_status("COMPLETED")
    assert terminal_run_status("FAILED")
    assert not terminal_run_status("RUNNING")


def test_parse_run_status() -> None:
    assert parse_run_status({"status": "done"}) == "DONE"


def test_classify_development_instruction() -> None:
    assert classify_assignment_instruction_kind("Refactor the auth helper") == "development"
    assert classify_assignment_instruction_kind("Summarize the CRM market") == "market_analysis"


def test_v0_post_shape_and_400_logs_response_body(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v0/agents"
        assert request.headers.get("authorization") == "Bearer test-key"
        body = __import__("json").loads(request.content.decode())
        assert body == {
            "prompt": {"text": "do a thing"},
            "source": {"repository": "https://github.com/o/r", "ref": "main"},
        }
        return httpx.Response(400, json={"error": "invalid repository", "hint": "use HTTPS"})

    transport = httpx.MockTransport(handler)
    client = CursorCloudClient(api_key="test-key", transport=transport)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(CursorApiError) as excinfo:
            client.create_agent_run(
                prompt_text="do a thing",
                repo_url="https://github.com/o/r",
                starting_ref="main",
                model_id=None,
                auto_create_pr=False,
            )
    assert "invalid repository" in caplog.text
    assert "invalid repository" in str(excinfo.value)


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def cursor_env(tmp_path_factory):
    root = tmp_path_factory.mktemp("cursor_repo")
    return {
        "CURSOR_ENABLED": "true",
        "CURSOR_API_KEY": "test-key",
        "CURSOR_DEFAULT_REPO_URL": "https://github.com/org/repo",
        "CURSOR_DEFAULT_BRANCH": "main",
        "CURSOR_POLL_INTERVAL_SECONDS": "0.01",
        "CURSOR_MAX_POLL_ITERATIONS": "2",
        "HOST_EXECUTOR_WORK_ROOT": str(root),
    }


def test_dispatch_routes_development_to_cursor(db_session, monkeypatch, cursor_env):
    from app.core import config as config_mod

    for k, v in cursor_env.items():
        monkeypatch.setenv(k, v)
    config_mod.get_settings.cache_clear()

    uid = f"u_cursor_{uuid.uuid4().hex[:10]}"
    from app.models.user import User

    db_session.merge(User(id=uid, timezone="UTC", is_new=False))
    db_session.commit()

    row = create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="coder",
        title="Fix lint",
        description="Refactor the helper",
        input_json={
            "user_message": "Refactor the helper module",
            "kind": "development",
            "task_type": "development",
            "source": "test",
        },
    )

    fake_create = {"agent": {"id": "a1"}, "run": {"id": "r1", "status": "COMPLETED"}}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def create_agent_run(self, **kwargs):
            return fake_create

        def get_run(self, **kwargs):
            return {"status": "COMPLETED"}

    with (
        patch("app.services.agent_team.service.try_assignment_host_dispatch", lambda *_a, **_k: None),
        patch("app.services.cursor_integration.cursor_runner.CursorCloudClient", FakeClient),
    ):
        out = dispatch_assignment(db_session, assignment_id=row.id, user_id=uid)

    assert out.get("ok") is True
    db_session.refresh(row)
    assert row.status == "completed"
    assert row.output_json and row.output_json.get("kind") == "cursor_cloud_agent"
    cur = row.output_json.get("cursor") or {}
    assert cur.get("cursor_run_id") == "r1"
    assert cur.get("cursor_agent_id") == "a1"

    types = {
        r.event_type
        for r in db_session.scalars(select(AuditLog).where(AuditLog.user_id == uid)).all()
    }
    assert "cursor.run.completed" in types

    config_mod.get_settings.cache_clear()


def test_dispatch_skips_cursor_when_disabled(db_session, monkeypatch, cursor_env):
    from app.core import config as config_mod

    monkeypatch.setenv("CURSOR_ENABLED", "false")
    for k, v in cursor_env.items():
        if k != "CURSOR_ENABLED":
            monkeypatch.setenv(k, v)
    config_mod.get_settings.cache_clear()

    uid = f"u_nocursor_{uuid.uuid4().hex[:10]}"
    from app.models.user import User

    db_session.merge(User(id=uid, timezone="UTC", is_new=False))
    db_session.add(
        UserAgent(
            owner_user_id=uid,
            agent_key="coder",
            display_name="Coder",
            description="",
            system_prompt="You code.",
        )
    )
    db_session.commit()

    row = create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="coder",
        title="Fix lint",
        description="Refactor",
        input_json={
            "user_message": "Refactor",
            "kind": "development",
            "task_type": "development",
            "source": "test",
        },
    )

    mock_run = MagicMock(return_value="hello from agent")
    with (
        patch("app.services.agent_team.service.try_assignment_host_dispatch", lambda *_a, **_k: None),
        patch("app.services.agent_team.service.run_custom_user_agent", mock_run),
    ):
        out = dispatch_assignment(db_session, assignment_id=row.id, user_id=uid)

    assert out.get("ok") is True
    mock_run.assert_called_once()

    config_mod.get_settings.cache_clear()

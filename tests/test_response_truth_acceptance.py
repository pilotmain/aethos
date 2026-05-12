# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Acceptance-style checks from docs/response truth finalization (integration + focused unit tests).

These map to: no fake assignment tone, dev-disabled clarity, real assignments, dedupe, @dev status, multi-agent.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal, ensure_schema
from app.core.security import get_valid_web_user_id
from app.main import app
from app.models.agent_team import AgentAssignment
from app.models.user import User
from app.services.agent_team.chat import try_agent_team_chat_turn
from app.services.agent_team.service import (
    DuplicateAssignmentError,
    create_assignment,
    get_or_create_default_organization,
)
from app.services.custom_agent_routing import is_create_custom_agent_request
from app.services.response_sanitizer import (
    reply_claims_assignment_without_evidence,
    sanitize_execution_and_assignment_reply,
)
from app.services.multi_agent_routing import (
    is_multi_agent_capability_question,
    reply_multi_agent_capability_clarification,
)


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_acceptance_1_plain_build_request_not_agent_team_turn(db_session) -> None:
    """Generic planning text does not hit deterministic agent-team routing."""
    assert (
        try_agent_team_chat_turn(
            db_session,
            "tg_unused",
            "build login system",
            web_session_id=None,
        )
        is None
    )


def test_acceptance_1_tracked_user_softens_fake_assignment_reply() -> None:
    """When user expects orchestration, assistant cannot imply assignment without an id uncorrected."""
    fake = "I've assigned @dev to build the login system."
    assert reply_claims_assignment_without_evidence(fake)
    out = sanitize_execution_and_assignment_reply(
        fake,
        user_text="@orchestrator build login system",
        related_job_ids=[],
    )
    assert "tracked assignment id" in out.lower() or "host job id" in out.lower()


@patch("app.services.response_sanitizer.get_settings")
def test_acceptance_2_dev_disabled_includes_phrase(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=False,
        cursor_enabled=False,
    )
    out = sanitize_execution_and_assignment_reply(
        "Use FastAPI for the API layer.",
        user_text="@dev build the login API with JWT",
    )
    assert "dev execution is not enabled" in out.lower()


def test_acceptance_3_assign_research_creates_row(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit assign with market-style instruction creates a durable assignment (no duplicate path)."""
    monkeypatch.setattr(
        "app.services.agent_team.chat.precheck_assignment_host_user_message",
        lambda *_a, **_k: (True, None),
    )

    def _mark_running(db, assignment_id, user_id):
        row = db_session.get(AgentAssignment, int(assignment_id))
        if row:
            row.status = "running"
            db_session.add(row)
            db_session.commit()
        return {"ok": True, "output": {"text": "stub"}}

    monkeypatch.setattr(
        "app.services.agent_team.chat.dispatch_assignment",
        _mark_running,
    )
    uid = f"acc_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    get_or_create_default_organization(db_session, uid)
    before = db_session.query(AgentAssignment).filter(AgentAssignment.user_id == uid).count()
    out = try_agent_team_chat_turn(
        db_session,
        uid,
        "assign @research-analyst to summarize market",
        web_session_id="default",
    )
    after = db_session.query(AgentAssignment).filter(AgentAssignment.user_id == uid).count()
    assert out is not None
    assert after == before + 1
    assert "assignment" in out.reply.lower() and "#" in out.reply


def test_acceptance_4_duplicate_create_raises(db_session) -> None:
    """Second create with same title+agent while first is active raises."""
    uid = f"acc_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    org = get_or_create_default_organization(db_session, uid)
    create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="research_analyst",
        title="summarize market",
        description="d",
        organization_id=org.id,
        input_json={},
    )
    with pytest.raises(DuplicateAssignmentError):
        create_assignment(
            db_session,
            user_id=uid,
            assigned_to_handle="research_analyst",
            title="summarize market",
            description="d2",
            organization_id=org.id,
            input_json={},
        )


def test_acceptance_4_post_agent_assignments_409() -> None:
    """API returns 409 when duplicate open assignment would be created."""
    uid = f"acc_{uuid.uuid4().hex[:12]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    try:
        client = TestClient(app)
        db = SessionLocal()
        try:
            db.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
            db.commit()
            org = get_or_create_default_organization(db, uid)
            org_id = int(org.id)
            create_assignment(
                db,
                user_id=uid,
                assigned_to_handle="research_analyst",
                title="api dedupe title",
                description="d",
                organization_id=org_id,
                input_json={},
            )
        finally:
            db.close()
        r2 = client.post(
            "/api/v1/agent-assignments",
            json={
                "organization_id": org_id,
                "assigned_to_handle": "research-analyst",
                "title": "api dedupe title",
                "description": "d2",
                "priority": "normal",
                "input_json": {},
            },
        )
        assert r2.status_code == 409
        body = r2.json()
        assert body.get("detail", {}).get("error") == "duplicate_assignment"
    finally:
        app.dependency_overrides.clear()


def test_acceptance_5_what_is_dev_working_on_empty(db_session) -> None:
    """@dev with no rows: honest empty state, no synthetic assignment."""
    uid = f"acc_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    get_or_create_default_organization(db_session, uid)
    out = try_agent_team_chat_turn(
        db_session,
        uid,
        "what is @dev working on?",
        web_session_id=None,
    )
    assert out is not None
    low = out.reply.lower()
    assert "no assignment" in low or "yet" in low or "no active" in low


def test_acceptance_6_multi_agent_overnight_not_custom_create() -> None:
    """Autonomy/overnight capability question routes to clarification, not greedy custom-agent create."""
    q = "can agents work autonomously overnight?"
    assert is_multi_agent_capability_question(q) is True
    assert is_create_custom_agent_request(q) is False
    clar = reply_multi_agent_capability_clarification().lower()
    assert "aethos" in clar and ("goal" in clar or "concrete" in clar)

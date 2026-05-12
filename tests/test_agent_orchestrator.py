# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Agent organization + assignment orchestration (V1)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal, ensure_schema
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.user_agent import UserAgent
from app.services.agent_team.chat import (
    agent_team_chat_blocks_folder_heuristics,
    try_agent_team_chat_turn,
)
from app.services.agent_team.planner import plan_tasks_from_goal
from app.services.agent_team.service import (
    create_assignment,
    dispatch_assignment,
    get_or_create_default_organization,
)
from app.services.local_file_intent import infer_local_file_request


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_plan_tasks_keyword_routes() -> None:
    plans = plan_tasks_from_goal("Review contract risk and legal liability.")
    handles = {p["assigned_to"] for p in plans}
    assert "legal-reviewer" in handles


def test_agent_team_blocks_local_folder_heuristic() -> None:
    assert agent_team_chat_blocks_folder_heuristics("ask my team to read ./foo")
    assert infer_local_file_request("ask my team to read ./foo").matched is False


def test_create_org_dispatch_custom_agent(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    uid = f"orch_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="Orch", timezone="UTC", is_new=False))
    db_session.commit()

    monkeypatch.setattr(
        "app.services.agent_team.service.try_assignment_host_dispatch",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "app.services.agent_team.service.run_custom_user_agent",
        lambda *_a, **_k: "**Done** (stub)",
    )

    org = get_or_create_default_organization(db_session, uid)
    assert org.id > 0

    db_session.add(
        UserAgent(
            owner_user_id=uid,
            agent_key="research_analyst",
            display_name="RA",
            description="",
            system_prompt="You are helpful.",
        )
    )
    db_session.commit()

    row = create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="research_analyst",
        title="Summarize",
        description="Market overview",
        organization_id=org.id,
        input_json={"user_message": "Summarize the CRM market."},
    )
    aid = row.id
    out = dispatch_assignment(db_session, assignment_id=aid, user_id=uid)
    assert out.get("ok") is True
    db_session.refresh(row)
    assert row.status == "completed"
    assert (row.output_json or {}).get("text")

    types = {
        r.event_type
        for r in db_session.scalars(select(AuditLog).where(AuditLog.user_id == uid)).all()
    }
    assert "agent_assignment.completed" in types


def test_try_team_chat_orchestrator_prefix_assign(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    uid = f"orch_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="Orch", timezone="UTC", is_new=False))
    db_session.commit()
    db_session.add(
        UserAgent(
            owner_user_id=uid,
            agent_key="research_analyst",
            display_name="RA",
            description="",
            system_prompt="You are helpful.",
        )
    )
    db_session.commit()
    monkeypatch.setattr(
        "app.services.agent_team.service.try_assignment_host_dispatch",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "app.services.agent_team.service.run_custom_user_agent",
        lambda *_a, **_k: "**Done** (stub)",
    )
    get_or_create_default_organization(db_session, uid)
    out = try_agent_team_chat_turn(
        db_session,
        uid,
        "@orchestrator assign @research_analyst to summarize this market: CRM tools",
        web_session_id=None,
    )
    assert out is not None
    assert out.reply and "Assignment" in out.reply


def test_try_team_chat_create_org_reply(db_session) -> None:
    uid = f"orch_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="Orch", timezone="UTC", is_new=False))
    db_session.commit()
    out = try_agent_team_chat_turn(
        db_session, uid, "create an agent team for sales", web_session_id=None
    )
    assert out and out.reply and "organization" in out.reply.lower()


def test_dispatch_missing_agent_fails(db_session) -> None:
    uid = f"orch_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="Orch", timezone="UTC", is_new=False))
    db_session.commit()
    org = get_or_create_default_organization(db_session, uid)
    row = create_assignment(
        db_session,
        user_id=uid,
        assigned_to_handle="nonexistent_agent",
        title="x",
        description="y",
        organization_id=org.id,
        input_json={},
    )
    out = dispatch_assignment(db_session, assignment_id=row.id, user_id=uid)
    assert out.get("ok") is False
    db_session.refresh(row)
    assert row.status == "failed"

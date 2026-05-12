# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""After SQL purge + reset-hard alias, Mission Control summary has no assignments."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.main import app
from app.models.agent_team import AgentAssignment
from app.models.user import User
from app.services.agent_team.service import get_or_create_default_organization


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_summary_empty_after_reset_hard(monkeypatch, db_session, tmp_path) -> None:
    monkeypatch.setenv("NEXA_MISSION_CONTROL_SQL_PURGE", "true")
    monkeypatch.setenv("NEXA_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "memory"))
    get_settings.cache_clear()

    uid = f"web_mc_rst_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    org = get_or_create_default_organization(db_session, uid)
    db_session.add(
        AgentAssignment(
            user_id=uid,
            organization_id=org.id,
            assigned_to_handle="dev",
            assigned_by_handle="orchestrator",
            title="x",
            description="d",
            status="completed",
            input_json={},
        )
    )
    db_session.commit()

    c = TestClient(app)
    r = c.post(
        "/api/v1/mission-control/reset-hard",
        headers={"X-User-Id": uid},
        json={
            "include_audit_logs": False,
            "include_pending_permissions": True,
            "include_custom_agents": False,
            "clear_workspace_files": True,
        },
    )
    assert r.status_code == 200, r.text

    s = c.get("/api/v1/mission-control/state?hours=24", headers={"X-User-Id": uid})
    assert s.status_code == 200, s.text
    body = s.json()
    orch = body.get("orchestration") or {}
    assigns = orch.get("assignments") or []
    assert assigns == []

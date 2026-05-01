"""Mission Control data inventory + gated SQL purge."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.main import app
from app.models.agent_team import AgentAssignment, AgentOrganization
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


def test_data_inventory_counts_assignments(db_session) -> None:
    uid = f"web_mc_inv_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
    org = get_or_create_default_organization(db_session, uid)
    db_session.add(
        AgentAssignment(
            user_id=uid,
            organization_id=org.id,
            assigned_to_handle="dev",
            assigned_by_handle="orchestrator",
            title="t",
            description="d",
            status="queued",
            input_json={},
        )
    )
    db_session.commit()

    c = TestClient(app)
    r = c.get("/api/v1/mission-control/data-inventory", headers={"X-User-Id": uid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == uid
    assert body["tables"]["agent_assignments"] >= 1


def test_purge_sql_forbidden_when_flag_off(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_MISSION_CONTROL_SQL_PURGE", "false")
    get_settings.cache_clear()
    c = TestClient(app)
    r = c.post(
        "/api/v1/mission-control/database/purge-sql",
        headers={"X-User-Id": "web_mc_prq_test"},
        json={},
    )
    assert r.status_code == 403


def test_purge_sql_deletes_rows_when_flag_on(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NEXA_MISSION_CONTROL_SQL_PURGE", "true")
    monkeypatch.setenv("NEXA_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "memory"))
    get_settings.cache_clear()

    uid = f"web_mc_sql_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
    org = get_or_create_default_organization(db_session, uid)
    db_session.add(
        AgentAssignment(
            user_id=uid,
            organization_id=org.id,
            assigned_to_handle="dev",
            assigned_by_handle="orchestrator",
            title="t",
            description="d",
            status="queued",
            input_json={},
        )
    )
    db_session.commit()

    c = TestClient(app)
    r = c.post(
        "/api/v1/mission-control/database/purge-sql",
        headers={"X-User-Id": uid},
        json={
            "include_audit_logs": False,
            "include_pending_permissions": True,
            "include_custom_agents": True,
            "clear_workspace_files": True,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["deleted"]["agent_assignments"] >= 1

    inv = c.get("/api/v1/mission-control/data-inventory", headers={"X-User-Id": uid})
    assert inv.json()["tables"]["agent_assignments"] == 0


def test_reset_hard_alias_matches_purge_sql(db_session, monkeypatch, tmp_path) -> None:
    """POST /reset-hard is an alias for POST /database/purge-sql with the same body."""
    monkeypatch.setenv("NEXA_MISSION_CONTROL_SQL_PURGE", "true")
    monkeypatch.setenv("NEXA_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "memory"))
    get_settings.cache_clear()

    uid = f"web_mc_rst_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
    org = get_or_create_default_organization(db_session, uid)
    db_session.add(
        AgentAssignment(
            user_id=uid,
            organization_id=org.id,
            assigned_to_handle="dev",
            assigned_by_handle="orchestrator",
            title="t",
            description="d",
            status="queued",
            input_json={},
        )
    )
    db_session.commit()

    body = {
        "include_audit_logs": False,
        "include_pending_permissions": True,
        "include_custom_agents": True,
        "clear_workspace_files": True,
    }
    c = TestClient(app)
    r = c.post("/api/v1/mission-control/reset-hard", headers={"X-User-Id": uid}, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["deleted"]["agent_assignments"] >= 1

    inv = c.get("/api/v1/mission-control/data-inventory", headers={"X-User-Id": uid})
    assert inv.json()["tables"]["agent_assignments"] == 0

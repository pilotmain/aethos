"""Mission Control cleanup API — assignments, spawn groups, reports, jobs, reset."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.main import app
from app.models.agent_job import AgentJob
from app.models.agent_team import AgentAssignment, AgentOrganization
from app.models.user import User
from app.services.agent_team.service import get_or_create_default_organization
from app.services.mission_control.cleanup_actions import delete_or_hide_assignment
from app.services.mission_control.read_model import build_mission_control_summary
from app.services.mission_control.ui_state import dismiss_attention_item, is_attention_dismissed


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXA_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    get_settings.cache_clear()
    yield TestClient(app)


def _seed_user(db_session, uid: str) -> None:
    db_session.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
    db_session.commit()


def test_assignment_delete_hides_from_summary(db_session) -> None:
    uid = f"web_mc_asg_{uuid.uuid4().hex[:12]}"
    _seed_user(db_session, uid)
    org = get_or_create_default_organization(db_session, uid)
    row = AgentAssignment(
        user_id=uid,
        organization_id=org.id,
        assigned_to_handle="dev",
        assigned_by_handle="orchestrator",
        title="Task — [spawn_mc_test]",
        description="d",
        status="queued",
        input_json={"spawn_group_id": "spawn_mc_test"},
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    summ_before = build_mission_control_summary(db_session, uid, hours=24)
    ids_before = [a["id"] for a in summ_before["orchestration"]["assignments"]]
    assert row.id in ids_before

    out = delete_or_hide_assignment(db_session, user_id=uid, assignment_id=row.id, hard_delete=False)
    assert out.get("ok") is True

    summ_after = build_mission_control_summary(db_session, uid, hours=24)
    ids_after = [a["id"] for a in summ_after["orchestration"]["assignments"]]
    assert row.id not in ids_after


def test_clear_spawn_group_cancels_assignments(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NEXA_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "memory"))
    get_settings.cache_clear()

    uid = f"web_mc_sg_{uuid.uuid4().hex[:12]}"
    _seed_user(db_session, uid)
    org = get_or_create_default_organization(db_session, uid)
    sg = f"spawn_mc_{uuid.uuid4().hex[:10]}"
    rows = []
    for i in range(3):
        r = AgentAssignment(
            user_id=uid,
            organization_id=org.id,
            assigned_to_handle="dev",
            assigned_by_handle="orchestrator",
            title=f"Work {i} — [{sg}]",
            description="d",
            status="queued",
            input_json={},
        )
        db_session.add(r)
        rows.append(r)
    db_session.commit()
    for r in rows:
        db_session.refresh(r)

    c = TestClient(app)
    r = c.post(
        f"/api/v1/mission-control/spawn-groups/{sg}/clear",
        headers={"X-User-Id": uid},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert len(body["cleared_assignments"]) == 3

    mc_path = Path(tmp_path) / "reports" / "mission_control.md"
    assert mc_path.is_file()
    text = mc_path.read_text()
    assert "No active missions" in text


def test_clear_report_writes_template(db_session, monkeypatch, tmp_path, api_client) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    mc = reports / "mission_control.md"
    mc.write_text("STALE", encoding="utf-8")
    tl = reports / "timeline.jsonl"
    tl.write_text('{"x":1}\n', encoding="utf-8")

    uid = f"web_mc_rep_{uuid.uuid4().hex[:12]}"
    _seed_user(db_session, uid)

    r = api_client.post("/api/v1/mission-control/reports/clear", headers={"X-User-Id": uid})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "mission_control.md" in data["cleared"]

    text = mc.read_text()
    assert "No active missions" in text
    assert tl.read_text() == ""


def test_reset_dismisses_jobs_and_hides_assignments(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NEXA_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "memory"))
    get_settings.cache_clear()

    uid = f"web_mc_rst_{uuid.uuid4().hex[:12]}"
    _seed_user(db_session, uid)
    org = get_or_create_default_organization(db_session, uid)
    a = AgentAssignment(
        user_id=uid,
        organization_id=org.id,
        assigned_to_handle="dev",
        assigned_by_handle="orchestrator",
        title="A1",
        description="d",
        status="queued",
        input_json={},
    )
    db_session.add(a)
    j = AgentJob(
        user_id=uid,
        source="web",
        kind="dev_task",
        worker_type="dev_executor",
        title="failed task",
        instruction="x",
        status="failed",
        approval_required=False,
        payload_json={},
    )
    db_session.add(j)
    db_session.commit()
    db_session.refresh(a)
    db_session.refresh(j)

    c = TestClient(app)
    r = c.post(
        "/api/v1/mission-control/reset",
        headers={"X-User-Id": uid},
        json={"include_custom_agents": False, "hard_delete": False},
    )
    assert r.status_code == 200, r.text
    summ = r.json()
    assert summ["assignments_cleared"] >= 1
    assert summ["jobs_dismissed"] >= 1

    db_session.refresh(j)
    pl = dict(j.payload_json or {})
    assert pl.get("dismissed_from_mission_control") is True


def test_purge_disables_custom_agents_and_sets_flag(db_session, monkeypatch, tmp_path) -> None:
    from app.models.user_agent import UserAgent

    monkeypatch.setenv("NEXA_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "memory"))
    get_settings.cache_clear()

    uid = f"web_mc_prg_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
    db_session.commit()
    ua = UserAgent(
        owner_user_id=uid,
        agent_key=f"purge_{uuid.uuid4().hex[:8]}",
        display_name="Purge",
        description="",
        system_prompt="x",
        allowed_tools_json="[]",
        safety_level="standard",
        is_active=True,
    )
    db_session.add(ua)
    db_session.commit()

    c = TestClient(app)
    r = c.post("/api/v1/mission-control/purge", headers={"X-User-Id": uid}, json={"hard_delete": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("purged") is True
    assert body.get("custom_agents_changed", 0) >= 1

    db_session.refresh(ua)
    assert ua.is_active is False


def test_reset_preserves_custom_agents_by_default(db_session, monkeypatch, tmp_path) -> None:
    from app.models.user_agent import UserAgent

    monkeypatch.setenv("NEXA_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "memory"))
    get_settings.cache_clear()

    uid = f"web_mc_cap_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
    db_session.commit()
    ua = UserAgent(
        owner_user_id=uid,
        agent_key=f"boss_{uuid.uuid4().hex[:8]}",
        display_name="Boss",
        description="",
        system_prompt="x",
        allowed_tools_json="[]",
        safety_level="standard",
        is_active=True,
    )
    db_session.add(ua)
    db_session.commit()

    c = TestClient(app)
    r = c.post(
        "/api/v1/mission-control/reset",
        headers={"X-User-Id": uid},
        json={"include_custom_agents": False, "hard_delete": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["custom_agents_changed"] == 0

    db_session.refresh(ua)
    assert ua.is_active is True


def test_assignment_delete_post_alias(api_client, db_session) -> None:
    """POST …/assignments/{id}/delete matches DELETE behavior (web UI uses POST for compatibility)."""
    uid = f"web_mc_post_{uuid.uuid4().hex[:12]}"
    _seed_user(db_session, uid)
    org = get_or_create_default_organization(db_session, uid)
    row = AgentAssignment(
        user_id=uid,
        organization_id=org.id,
        assigned_to_handle="dev",
        assigned_by_handle="orchestrator",
        title="Post delete test",
        description="d",
        status="queued",
        input_json={},
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    r = api_client.post(
        f"/api/v1/mission-control/assignments/{row.id}/delete",
        headers={"X-User-Id": uid},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    # API uses its own DB session; expire cached rows before re-querying in this session.
    db_session.expire_all()
    summ = build_mission_control_summary(db_session, uid, hours=24)
    ids_after = [a["id"] for a in summ["orchestration"]["assignments"]]
    assert row.id not in ids_after


def test_custom_agent_delete_via_mission_control(api_client, db_session) -> None:
    from app.models.user_agent import UserAgent

    uid = f"web_mc_del_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
    ak = f"helper_{uuid.uuid4().hex[:8]}"
    ua = UserAgent(
        owner_user_id=uid,
        agent_key=ak,
        display_name="Helper",
        description="",
        system_prompt="x",
        allowed_tools_json="[]",
        safety_level="standard",
        is_active=True,
    )
    db_session.add(ua)
    db_session.commit()

    r = api_client.delete(f"/api/v1/mission-control/custom-agents/{ak}", headers={"X-User-Id": uid})
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "disabled"

    db_session.refresh(ua)
    assert ua.is_active is False


def test_attention_dismiss_persisted(db_session) -> None:
    uid = f"web_mc_att_{uuid.uuid4().hex[:12]}"
    dismiss_attention_item(uid, "trust-999")
    assert is_attention_dismissed(uid, "trust-999") is True


def test_job_dismiss_api(api_client, db_session) -> None:
    uid = f"web_mc_job_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
    j = AgentJob(
        user_id=uid,
        source="web",
        kind="dev_task",
        worker_type="dev_executor",
        title="t",
        instruction="x",
        status="failed",
        approval_required=False,
        payload_json={},
    )
    db_session.add(j)
    db_session.commit()
    db_session.refresh(j)

    r = api_client.post(f"/api/v1/mission-control/jobs/{j.id}/dismiss", headers={"X-User-Id": uid})
    assert r.status_code == 200, r.text
    assert r.json()["dismissed"] is True

    db_session.expire_all()
    summ = build_mission_control_summary(db_session, uid, hours=24)
    job_ids_in_attention = [
        x.get("job_id") for x in summ["attention"] if x.get("type") == "failed_job"
    ]
    assert j.id not in job_ids_in_attention

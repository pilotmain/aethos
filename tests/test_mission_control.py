"""Mission Control V1 API tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.access_permission import AccessPermission
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.access_permissions import RISK_MEDIUM, STATUS_PENDING
from app.services.mission_control.scoring import score_mission_item
from app.services.trust_audit_constants import ACCESS_SENSITIVE_EGRESS_WARNING, NETWORK_EXTERNAL_SEND_BLOCKED


def test_mission_control_state_includes_autonomy_phase44(api_client: tuple[TestClient, str]) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/mission-control/state?hours=24")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("autonomous_tasks"), list)
    assert isinstance(body.get("autonomy_decisions"), list)
    assert isinstance(body.get("autonomy_feedback"), list)
    assert isinstance(body.get("autonomy_execution_stats"), dict)


def test_mission_control_state_shape(api_client: tuple[TestClient, str]) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/mission-control/state?hours=24")
    assert r.status_code == 200
    body = r.json()
    assert "missions" in body and isinstance(body["missions"], list)
    assert "tasks" in body and isinstance(body["tasks"], list)
    assert "artifacts" in body and isinstance(body["artifacts"], list)
    assert "events" in body and isinstance(body["events"], list)
    assert "privacy_events" in body and isinstance(body["privacy_events"], list)
    assert "provider_events" in body and isinstance(body["provider_events"], list)
    assert "last_updated" in body
    assert "overview" in body
    assert "orchestration" in body
    assert "maintenance" in body
    assert "sql_purge_enabled" in body["maintenance"]


def test_unified_state_dashboard_shape(api_client: tuple[TestClient, str]) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/mission-control/state?hours=24")
    assert r.status_code == 200
    body = r.json()
    assert "attention" in body
    assert "active_work" in body
    assert "pending_approvals" in body
    assert "risk_summary" in body
    assert "channels" in body
    assert "recommendations" in body
    orch = body["orchestration"]
    assert isinstance(orch.get("assignments"), list)
    ov = body["overview"]
    for k in (
        "active_jobs",
        "pending_approvals",
        "blocked_actions",
        "high_risk_events",
        "active_channels",
        "recent_executions",
    ):
        assert k in ov
        assert isinstance(ov[k], int)


def test_pending_approval_in_attention(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    db = SessionLocal()
    try:
        db.merge(
            User(
                id=uid,
                name="MC",
                timezone="UTC",
                is_new=False,
            )
        )
        db.add(
            AccessPermission(
                owner_user_id=uid,
                scope="file_read",
                target="/tmp/x",
                risk_level=RISK_MEDIUM,
                status=STATUS_PENDING,
            )
        )
        db.commit()
    finally:
        db.close()

    r = client.get("/api/v1/mission-control/state?hours=24")
    assert r.status_code == 200
    body = r.json()
    assert body["overview"]["pending_approvals"] >= 1
    types = {x.get("type") for x in body["attention"]}
    assert "pending_approval" in types


def test_blocked_trust_in_attention(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    db = SessionLocal()
    try:
        db.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
        db.add(
            AuditLog(
                user_id=uid,
                event_type=NETWORK_EXTERNAL_SEND_BLOCKED,
                actor="test",
                message="blocked send",
                metadata_json={"hostname": "evil.example"},
            )
        )
        db.commit()
    finally:
        db.close()

    r = client.get("/api/v1/mission-control/state?hours=24")
    assert r.status_code == 200
    titles = " ".join(x.get("title", "") for x in r.json()["attention"])
    assert "Blocked" in titles or "blocked" in titles.lower()


def test_scoring_prioritizes_approvals(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    db = SessionLocal()
    try:
        db.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
        db.add(
            AccessPermission(
                owner_user_id=uid,
                scope="network_request",
                target="https://a",
                risk_level=RISK_MEDIUM,
                status=STATUS_PENDING,
            )
        )
        db.add(
            AuditLog(
                user_id=uid,
                event_type=ACCESS_SENSITIVE_EGRESS_WARNING,
                actor="test",
                message="sensitive",
                metadata_json={},
            )
        )
        db.commit()
    finally:
        db.close()

    r = client.get("/api/v1/mission-control/state?hours=24")
    att = r.json()["attention"]
    assert len(att) >= 2
    assert score_mission_item({"type": "pending_approval"}) > score_mission_item({"type": "sensitive_warning"})
    # Highest-score item first after sort
    assert att[0].get("type") == "pending_approval"


def test_missing_channel_recommendation(monkeypatch: pytest.MonkeyPatch, api_client: tuple[TestClient, str]) -> None:
    client, _uid = api_client

    def _fake_status() -> list[dict]:
        return [
            {
                "channel": "email",
                "label": "Email",
                "available": True,
                "configured": False,
                "enabled": False,
                "health": "missing_config",
                "webhook_url": None,
                "webhook_urls": None,
                "missing": ["SMTP_HOST"],
                "notes": [],
            }
        ]

    monkeypatch.setattr(
        "app.services.mission_control.read_model.build_channel_status_list",
        _fake_status,
    )
    monkeypatch.setattr(
        "app.services.mission_control.read_model.merge_channel_status_governance",
        lambda _db, rows, organization_id=None: rows,
    )

    r = client.get("/api/v1/mission-control/state?hours=24")
    assert r.status_code == 200
    recs = r.json().get("recommendations") or []
    texts = " ".join(str(x.get("title", "")) for x in recs)
    assert "Email" in texts or "email" in texts.lower()


def test_quiet_state_safe(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    db = SessionLocal()
    try:
        db.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
        db.commit()
    finally:
        db.close()
    r = client.get("/api/v1/mission-control/state?hours=1")
    assert r.status_code == 200
    body = r.json()
    assert body.get("quiet") is True
    assert isinstance(body["attention"], list)


def test_orchestration_includes_db_assignment_id(api_client: tuple[TestClient, str]) -> None:
    """Mission Control assignment rows come from the same list as the agent-team service (no synthetic rows)."""
    from app.services.agent_team.service import create_assignment, get_or_create_default_organization

    client, uid = api_client
    db = SessionLocal()
    try:
        db.merge(User(id=uid, name="MC", timezone="UTC", is_new=False))
        db.commit()
        org = get_or_create_default_organization(db, uid)
        row = create_assignment(
            db,
            user_id=uid,
            assigned_to_handle="research_analyst",
            title="Mission control DB-backed title",
            description="d",
            organization_id=org.id,
            input_json={},
        )
        expect_id = row.id
    finally:
        db.close()
    r = client.get("/api/v1/mission-control/state?hours=24")
    assert r.status_code == 200
    assigns = (r.json().get("orchestration") or {}).get("assignments") or []
    match = [a for a in assigns if int(a.get("id") or 0) == expect_id]
    assert match
    assert match[0].get("title") == "Mission control DB-backed title"


def test_requires_identity() -> None:
    app.dependency_overrides.clear()
    try:
        client = TestClient(app)
        r = client.get("/api/v1/mission-control/state")
        assert r.status_code == 401
    finally:
        pass


def test_summary_endpoint_is_gone(api_client: tuple[TestClient, str]) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/mission-control/summary")
    assert r.status_code == 410

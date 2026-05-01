"""Phase 13: org channel policy, RBAC, audit export, retention, status merge."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.db import Base, SessionLocal
from app.core.security import get_valid_web_user_id
from app.main import app
from app.models.access_permission import AccessPermission
from app.models.audit_log import AuditLog
from app.models.audit_retention_policy import AuditRetentionPolicy
from app.models.organization_channel_policy import OrganizationChannelPolicy
from app.models.user import User
from app.services.access_permissions import RISK_HIGH, STATUS_GRANTED, STATUS_PENDING, grant_permission
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.governance_taxonomy import (
    EVENT_APPROVAL_ROLE_DENIED,
    EVENT_AUDIT_EXPORT_CREATED,
    EVENT_CHANNEL_ACCESS_DENIED,
)


@pytest.fixture
def mem_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine, class_=Session, future=True)
    db = S()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _user(
    uid: str,
    *,
    org: str | None = "org_1",
    role: str | None = "admin",
) -> User:
    return User(
        id=uid,
        name="T",
        timezone="UTC",
        is_new=False,
        organization_id=org,
        governance_role=role,
    )


def test_1_channel_disabled_slack_no_policy(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.governance.get_settings",
        lambda: SimpleNamespace(nexa_governance_enabled=True, nexa_default_organization_id=None),
    )
    mem_db.add(_user("gov_u_slack", org="org_1", role="admin"))
    mem_db.commit()
    msg = {
        "channel": "slack",
        "channel_user_id": "c1",
        "user_id": "gov_u_slack",
        "message": "hi",
        "attachments": [],
        "metadata": {},
    }
    with patch("app.services.web_chat_service.process_web_message") as pm:
        out = handle_incoming_channel_message(mem_db, normalized_message=msg)
    assert out["response_kind"] == "governance_denied"
    pm.assert_not_called()
    last = mem_db.scalars(select(AuditLog).order_by(desc(AuditLog.id)).limit(1)).first()
    assert last is not None
    assert last.event_type == EVENT_CHANNEL_ACCESS_DENIED


def test_2_role_viewer_not_allowed_web(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.governance.get_settings",
        lambda: SimpleNamespace(nexa_governance_enabled=True, nexa_default_organization_id=None),
    )
    mem_db.add(_user("gov_u_viewer", org="org_1", role="viewer"))
    mem_db.add(
        OrganizationChannelPolicy(
            organization_id="org_1",
            channel="web",
            enabled=True,
            allowed_roles=["operator"],
            approval_required=False,
        )
    )
    mem_db.commit()
    msg = {
        "channel": "web",
        "channel_user_id": "c1",
        "user_id": "gov_u_viewer",
        "message": "hi",
        "attachments": [],
        "metadata": {},
    }
    with patch("app.services.web_chat_service.process_web_message") as pm:
        out = handle_incoming_channel_message(mem_db, normalized_message=msg)
    assert out["response_kind"] == "governance_denied"
    pm.assert_not_called()


def test_3_operator_allowed_web(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.governance.get_settings",
        lambda: SimpleNamespace(nexa_governance_enabled=True, nexa_default_organization_id=None),
    )
    mem_db.add(_user("gov_u_op", org="org_1", role="operator"))
    mem_db.add(
        OrganizationChannelPolicy(
            organization_id="org_1",
            channel="web",
            enabled=True,
            allowed_roles=["operator"],
            approval_required=False,
        )
    )
    mem_db.commit()
    msg = {
        "channel": "web",
        "channel_user_id": "c1",
        "user_id": "gov_u_op",
        "message": "hi",
        "attachments": [],
        "metadata": {},
    }
    mock_res = MagicMock(
        reply="ok",
        response_kind="chat",
        permission_required=None,
        intent=None,
        agent_key=None,
        related_job_ids=[],
        sources=[],
        web_tool_line=None,
        usage_summary=None,
        request_id=None,
        decision_summary=None,
        system_events=[],
    )
    with patch("app.services.web_chat_service.process_web_message", return_value=mock_res) as pm:
        out = handle_incoming_channel_message(mem_db, normalized_message=msg)
    pm.assert_called_once()
    assert out["response_kind"] == "chat"
    assert "ok" in (out.get("message") or "")


def _gov_on_settings() -> SimpleNamespace:
    return SimpleNamespace(
        nexa_governance_enabled=True,
        nexa_default_organization_id=None,
        nexa_auto_create_default_org=False,
    )


def test_4_high_risk_approval_role_denied(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    # Each module binds its own `get_settings` import — patch both enforcement sites.
    monkeypatch.setattr("app.services.access_permissions.get_settings", _gov_on_settings)
    monkeypatch.setattr("app.services.channel_gateway.governance.get_settings", _gov_on_settings)
    mem_db.add(_user("gov_owner", org="org_1", role="operator"))
    mem_db.add(
        AccessPermission(
            owner_user_id="gov_owner",
            scope="network_request",
            target="https://ex",
            risk_level=RISK_HIGH,
            status=STATUS_PENDING,
        )
    )
    mem_db.commit()
    perm = mem_db.scalars(select(AccessPermission)).first()
    assert perm is not None
    out = grant_permission(
        mem_db,
        "gov_owner",
        perm.id,
        granted_by_user_id="other_user",
    )
    assert out is None
    row = mem_db.scalars(select(AuditLog).order_by(desc(AuditLog.id)).limit(1)).first()
    assert row is not None
    assert row.event_type == EVENT_APPROVAL_ROLE_DENIED


def test_5_audit_export_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_GOVERNANCE_ENABLED", "true")
    get_settings.cache_clear()
    uid = f"gov_export_json_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        u = _user(uid, org="org_1", role="auditor")
        db.add(u)
        db.add(
            AuditLog(
                user_id="u99",
                event_type="test.event",
                actor="t",
                message="m1",
                metadata_json={"channel": "slack", "status": "ok"},
            )
        )
        db.commit()
        app.dependency_overrides[get_valid_web_user_id] = lambda: uid
        client = TestClient(app)
        r = client.get("/api/v1/audit/export?format=json")
        assert r.status_code == 200
        body = r.json()
        assert "events" in body
        types = {e["event_type"] for e in body["events"]}
        assert "test.event" in types
        log_row = db.scalars(
            select(AuditLog).where(AuditLog.event_type == EVENT_AUDIT_EXPORT_CREATED).order_by(desc(AuditLog.id)).limit(1)
        ).first()
        assert log_row is not None
    finally:
        db.close()
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_GOVERNANCE_ENABLED", raising=False)
        get_settings.cache_clear()


def test_6_audit_export_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_GOVERNANCE_ENABLED", "true")
    get_settings.cache_clear()
    uid = f"gov_export_csv_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        u = _user(uid, org="org_1", role="auditor")
        db.add(u)
        db.add(
            AuditLog(
                user_id="u88",
                event_type="csv.probe",
                actor="t",
                message="m2",
                metadata_json={"channel": "whatsapp"},
            )
        )
        db.commit()
        app.dependency_overrides[get_valid_web_user_id] = lambda: uid
        client = TestClient(app)
        r = client.get("/api/v1/audit/export?format=csv")
        assert r.status_code == 200
        text = r.text
        assert "channel" in text.lower()
        assert "csv.probe" in text or "event_type" in text
    finally:
        db.close()
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_GOVERNANCE_ENABLED", raising=False)
        get_settings.cache_clear()


def test_7_retention_read_write(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_GOVERNANCE_ENABLED", "true")
    get_settings.cache_clear()
    oid = f"org_rw_{uuid.uuid4().hex[:8]}"
    uid = f"gov_ret_admin_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        u = _user(uid, org=oid, role="admin")
        db.add(u)
        db.commit()
        app.dependency_overrides[get_valid_web_user_id] = lambda: uid
        client = TestClient(app)
        r = client.patch(
            "/api/v1/governance/retention",
            json={"organization_id": oid, "retention_days": 180},
        )
        assert r.status_code == 200
        assert r.json()["retention_days"] == 180
        row = db.get(AuditRetentionPolicy, oid)
        assert row is not None
        assert row.retention_days == 180
    finally:
        db.close()
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_GOVERNANCE_ENABLED", raising=False)
        get_settings.cache_clear()


def test_8_channel_status_has_governance_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_GOVERNANCE_ENABLED", "true")
    get_settings.cache_clear()
    oid = f"org_stat_{uuid.uuid4().hex[:8]}"
    uid = f"gov_status_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        u = _user(uid, org=oid, role="admin")
        db.add(u)
        db.add(
            OrganizationChannelPolicy(
                organization_id=oid,
                channel="slack",
                enabled=True,
                allowed_roles=["owner", "admin", "operator"],
                approval_required=True,
            )
        )
        db.commit()
        app.dependency_overrides[get_valid_web_user_id] = lambda: uid
        client = TestClient(app)
        r = client.get(f"/api/v1/channels/status?organization_id={oid}")
        assert r.status_code == 200
        chans = {c["channel"]: c for c in r.json()["channels"]}
        s = chans["slack"]
        assert s.get("allowed_roles") == ["owner", "admin", "operator"]
        assert s.get("approval_required") is True
        assert s.get("governance_enabled") is True
    finally:
        db.close()
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_GOVERNANCE_ENABLED", raising=False)
        get_settings.cache_clear()


def test_grant_high_risk_succeeds_for_approver(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.access_permissions.get_settings", _gov_on_settings)
    monkeypatch.setattr("app.services.channel_gateway.governance.get_settings", _gov_on_settings)
    mem_db.add(_user("gov_owner2", org="org_1", role="operator"))
    mem_db.add(_user("gov_approver", org="org_1", role="approver"))
    mem_db.add(
        AccessPermission(
            owner_user_id="gov_owner2",
            scope="network_request",
            target="https://ex",
            risk_level=RISK_HIGH,
            status=STATUS_PENDING,
        )
    )
    mem_db.commit()
    perm = mem_db.scalars(select(AccessPermission)).first()
    assert perm is not None
    out = grant_permission(
        mem_db,
        "gov_owner2",
        perm.id,
        granted_by_user_id="gov_approver",
    )
    assert out is not None
    assert out.status == STATUS_GRANTED

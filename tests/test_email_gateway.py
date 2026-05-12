# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 7: Email channel adapter, router, SMTP, permission links, audit."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models.access_permission import AccessPermission
from app.models.audit_log import AuditLog
from app.models.channel_user import ChannelUser
from app.services.channel_gateway.email_adapter import EmailAdapter, email_default_user_id
from app.services.channel_gateway.email_links import build_email_permission_links, format_email_permission_text
from app.services.channel_gateway.email_token import email_permission_token, verify_email_permission_token
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.audit_service import audit
from app.services.permission_resume_execution import PermissionResumeError
from app.services.access_permissions import RISK_LOW, SCOPE_FILE_READ, STATUS_PENDING
from app.services.web_chat_service import WebChatResult
from app.services.web_user_id import validate_web_user_id


@pytest.fixture
def mem_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine, class_=Session, future=True)
    db = S()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_email_default_user_id_format_and_validation() -> None:
    uid = email_default_user_id("User@Example.com")
    assert uid.startswith("em_")
    assert validate_web_user_id(uid) == uid
    assert not uid.startswith("tg_")


def test_email_adapter_normalize(mem_db: Session) -> None:
    adapter = EmailAdapter()
    raw = {
        "from": "alice@example.com",
        "subject": "Hello",
        "text": "list files",
        "message_id": "mid-1",
        "thread_id": "th-9",
    }
    au = adapter.resolve_app_user_id(mem_db, raw)
    n = adapter.normalize_message(raw, app_user_id=au)
    assert n["channel"] == "email"
    assert n["channel_user_id"] == "alice@example.com"
    assert n["message"] == "list files"
    assert n["metadata"]["subject"] == "Hello"
    assert n["metadata"]["email_from"] == "alice@example.com"
    assert n["metadata"]["channel_message_id"] == "mid-1"
    assert n["metadata"]["channel_thread_id"] == "th-9"


def test_email_identity_channel_user(mem_db: Session) -> None:
    adapter = EmailAdapter()
    raw = {"from": "bob@example.com", "text": "hi"}
    u1 = adapter.resolve_app_user_id(mem_db, raw)
    u2 = adapter.resolve_app_user_id(mem_db, raw)
    assert u1 == u2
    row = mem_db.scalar(
        select(ChannelUser).where(
            ChannelUser.channel == "email",
            ChannelUser.channel_user_id == "bob@example.com",
        )
    )
    assert row is not None
    assert row.user_id == u1


@patch("app.services.channel_gateway.router.check_channel_governance", return_value=None)
@patch("app.services.web_chat_service.process_web_message")
def test_router_email_to_core(mock_core: MagicMock, _mock_gov: MagicMock, mem_db: Session) -> None:
    mock_core.return_value = WebChatResult(reply="ok", intent="chat", agent_key="nexa")
    norm = {
        "channel": "email",
        "channel_user_id": "u@x.com",
        "user_id": "em_" + "a" * 32,
        "message": "ping",
        "attachments": [],
        "metadata": {
            "channel_message_id": "m1",
            "channel_thread_id": "t1",
            "web_session_id": "email:t1",
        },
    }
    out = handle_incoming_channel_message(mem_db, normalized_message=norm)
    assert mock_core.called
    assert out["metadata"]["channel"] == "email"
    assert out["metadata"]["channel_user_id"] == "u@x.com"


@patch("app.services.channel_gateway.email_adapter.send_smtp_email")
def test_email_adapter_send_message_triggers_smtp(mock_send: MagicMock, mem_db: Session) -> None:
    adapter = EmailAdapter()
    raw = {"from": "s@x.com", "text": "x"}
    uid = adapter.resolve_app_user_id(mem_db, raw)
    adapter.send_message(mem_db, uid, "body", subject="Sub")
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["to_addr"] == "s@x.com"


def test_permission_links_contain_api_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        api_base_url="https://api.example.com",
        api_v1_prefix="/api/v1",
        email_webhook_secret="sec_for_links",
    )

    def _gs():
        return s

    monkeypatch.setattr("app.services.channel_gateway.email_links.get_settings", _gs)
    monkeypatch.setattr("app.core.config.get_settings", _gs)
    links = build_email_permission_links(7, "em_" + "b" * 32)
    assert "/permissions/requests/7/email-approve" in links["once"]
    assert "mode=once" in links["once"]
    assert "mode=session" in links["session"]
    assert "/permissions/requests/7/email-deny" in links["deny"]
    txt = format_email_permission_text(7, "em_" + "b" * 32)
    assert "email-approve" in txt and "email-deny" in txt


def test_permission_links_missing_secret_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        api_base_url="http://localhost:8000",
        api_v1_prefix="/api/v1",
        email_webhook_secret="",
    )

    def _gs():
        return s

    monkeypatch.setattr("app.services.channel_gateway.email_links.get_settings", _gs)
    assert build_email_permission_links(1, "em_" + "c" * 32) == {}


def test_email_permission_hmac_roundtrip() -> None:
    owner = "em_" + "ab" * 16
    tok = email_permission_token("abc", 42, owner)
    assert verify_email_permission_token("abc", 42, owner, tok)
    assert not verify_email_permission_token("wrong", 42, owner, tok)


def test_audit_email_origin(mem_db: Session) -> None:
    norm = {
        "channel": "email",
        "channel_user_id": "z@z.com",
        "user_id": "em_" + "e" * 32,
        "message": "m",
        "attachments": [],
        "metadata": {},
    }
    with bind_channel_origin(build_channel_origin(norm)):
        audit(mem_db, event_type="test.email", actor="t", user_id="em_" + "e" * 32, message="x", metadata={})
    row = mem_db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    assert row is not None
    md = dict(row.metadata_json or {})
    assert md.get("channel") == "email"
    assert md.get("channel_user_id") == "z@z.com"


def _session_local_for(db: Session):
    def _factory() -> Session:
        return db

    return _factory


def _bind_settings(monkeypatch: pytest.MonkeyPatch, s: SimpleNamespace) -> None:
    """Patch ``get_settings`` in every module that imported it by name (not only ``app.core.config``)."""

    def _gs():
        return s

    monkeypatch.setattr("app.core.config.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.email_smtp.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.email_links.get_settings", _gs)
    monkeypatch.setattr("app.api.routes.email.get_settings", _gs)
    monkeypatch.setattr("app.api.routes.permissions.get_settings", _gs)


def _settings_email(monkeypatch: pytest.MonkeyPatch, *, secret: str = "whsec") -> None:
    s = SimpleNamespace(
        email_webhook_secret=secret,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        email_from="nexa@example.com",
        api_v1_prefix="/api/v1",
        api_base_url="http://test",
    )
    _bind_settings(monkeypatch, s)


@patch("app.api.routes.email.handle_incoming_channel_message")
@patch("app.api.routes.email.send_smtp_email")
def test_email_inbound_webhook_flow(
    mock_smtp: MagicMock,
    mock_handle: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mem_db: Session,
) -> None:
    _settings_email(monkeypatch)
    monkeypatch.setattr("app.api.routes.email.SessionLocal", _session_local_for(mem_db))
    mock_handle.return_value = {
        "message": "hello back",
        "permission_required": {"permission_request_id": 99, "reason": "run"},
        "response_kind": "permission_required",
    }
    c = TestClient(app)
    r = c.post(
        "/api/v1/email/inbound",
        json={
            "from": "in@example.com",
            "subject": "Q",
            "text": "ping",
            "message_id": "m",
        },
        headers={"X-Email-Webhook-Secret": "whsec"},
    )
    assert r.status_code == 200
    mock_handle.assert_called_once()
    body = mock_smtp.call_args.kwargs.get("body") or ""
    assert "hello back" in body
    assert "/permissions/requests/99/email-approve" in body
    assert mock_smtp.call_args.kwargs["subject"] == "Re: Q"


def test_email_inbound_rejects_bad_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings_email(monkeypatch)
    c = TestClient(app)
    r = c.post(
        "/api/v1/email/inbound",
        json={"from": "a@b.com", "text": "x"},
        headers={"X-Email-Webhook-Secret": "nope"},
    )
    assert r.status_code == 401


def test_email_approve_link_get(monkeypatch: pytest.MonkeyPatch, mem_db: Session) -> None:
    secret = "sharedsecret"
    _settings_email(monkeypatch, secret=secret)
    owner = email_default_user_id("owner@example.com")
    mem_db.add(
        AccessPermission(
            owner_user_id=owner[:64],
            scope=SCOPE_FILE_READ,
            target="/tmp",
            risk_level=RISK_LOW,
            status=STATUS_PENDING,
            reason="t",
        )
    )
    mem_db.commit()
    row = mem_db.scalars(select(AccessPermission).order_by(AccessPermission.id.desc()).limit(1)).first()
    assert row is not None
    pid = int(row.id)
    tok = email_permission_token(secret, pid, owner)

    def _db_override():
        yield mem_db

    app.dependency_overrides[get_db] = _db_override
    try:
        with patch(
            "app.api.routes.permissions.resume_host_executor_after_grant",
            side_effect=PermissionResumeError("no host job in test"),
        ):
            c = TestClient(app)
            r = c.get(
                f"/api/v1/permissions/requests/{pid}/email-approve",
                params={"token": tok, "mode": "once"},
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert "Permission updated" in r.text or "Permission granted" in r.text

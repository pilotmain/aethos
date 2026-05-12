# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 11: Apple Messages for Business (provider) adapter, webhook, audit, status."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.main import app
from app.models.audit_log import AuditLog
from app.models.channel_user import ChannelUser
from app.services.audit_service import audit
from app.services.channel_gateway.apple_messages_adapter import (
    AppleMessagesAdapter,
    apple_messages_default_user_id,
    json_payload_to_raw_event,
)
from app.services.channel_gateway.apple_messages_verify import verify_apple_messages_webhook_secret
from app.services.channel_gateway.email_links import format_email_permission_text
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.status import build_channel_status_list
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


def test_default_am_user_id_stability() -> None:
    u1 = apple_messages_default_user_id("customer_abc")
    u2 = apple_messages_default_user_id("customer_abc")
    assert u1 == u2
    assert u1.startswith("am_")
    assert validate_web_user_id(u1) == u1
    u3 = apple_messages_default_user_id("customer_xyz")
    assert u1 != u3


def test_json_payload_to_raw() -> None:
    raw = json_payload_to_raw_event(
        {
            "provider": "apple_business_messages",
            "customer_id": "customer_123",
            "conversation_id": "conversation_456",
            "message_id": "message_789",
            "text": "hello",
        }
    )
    assert raw["customer_id"] == "customer_123"
    assert raw["conversation_id"] == "conversation_456"


def test_channel_user_reuse(mem_db: Session) -> None:
    adapter = AppleMessagesAdapter()
    raw = {
        "customer_id": "cust_stable",
        "conversation_id": "conv1",
        "message_id": "m1",
        "text": "a",
    }
    a1 = adapter.resolve_app_user_id(mem_db, raw)
    a2 = adapter.resolve_app_user_id(mem_db, raw)
    assert a1 == a2
    row = mem_db.scalar(
        select(ChannelUser).where(
            ChannelUser.channel == "apple_messages",
            ChannelUser.channel_user_id == "cust_stable",
        )
    )
    assert row is not None


def test_normalize_inbound_shape(mem_db: Session) -> None:
    adapter = AppleMessagesAdapter()
    raw = {
        "customer_id": "customer_123",
        "conversation_id": "conversation_456",
        "message_id": "message_789",
        "text": "  hi  ",
        "provider": "apple_business_messages",
    }
    uid = adapter.resolve_app_user_id(mem_db, raw)
    n = adapter.normalize_message(raw, app_user_id=uid)
    assert n["channel"] == "apple_messages"
    assert n["channel_user_id"] == "customer_123"
    assert n["message"] == "hi"
    m = n["metadata"]
    assert m["channel_message_id"] == "message_789"
    assert m["channel_chat_id"] == "conversation_456"
    assert m["channel_thread_id"] == "conversation_456"
    assert m["customer_id"] == "customer_123"
    assert m["provider"] == "apple_business_messages"


@patch("app.services.channel_gateway.router.check_channel_governance", return_value=None)
@patch("app.services.web_chat_service.process_web_message")
def test_router_apple_to_core(mock_core: MagicMock, _mock_gov: MagicMock, mem_db: Session) -> None:
    mock_core.return_value = WebChatResult(reply="ok", intent="chat", agent_key="nexa")
    norm = {
        "channel": "apple_messages",
        "channel_user_id": "c1",
        "user_id": "am_" + "a" * 32,
        "message": "ping",
        "attachments": [],
        "metadata": {
            "channel_message_id": "m1",
            "channel_chat_id": "conv",
            "channel_thread_id": "conv",
            "web_session_id": "apple_messages:c1",
        },
    }
    out = handle_incoming_channel_message(mem_db, normalized_message=norm)
    assert mock_core.called
    assert out["metadata"]["channel"] == "apple_messages"
    assert out["metadata"]["channel_user_id"] == "c1"


def test_audit_apple_origin(mem_db: Session) -> None:
    norm = {
        "channel": "apple_messages",
        "channel_user_id": "customer_123",
        "user_id": "am_" + "b" * 32,
        "message": "m",
        "attachments": [],
        "metadata": {
            "channel_message_id": "message_789",
            "channel_chat_id": "conversation_456",
            "channel_thread_id": "conversation_456",
        },
    }
    with bind_channel_origin(build_channel_origin(norm)):
        audit(
            mem_db,
            event_type="test.am",
            actor="t",
            user_id="am_" + "b" * 32,
            message="x",
            metadata={},
        )
    row = mem_db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    assert row is not None
    md = dict(row.metadata_json or {})
    assert md.get("channel") == "apple_messages"
    assert md.get("channel_user_id") == "customer_123"
    assert md.get("channel_message_id") == "message_789"
    assert md.get("channel_chat_id") == "conversation_456"


def test_webhook_secret_header() -> None:
    assert verify_apple_messages_webhook_secret(
        configured_secret="abc",
        header_value="abc",
    )
    assert not verify_apple_messages_webhook_secret(
        configured_secret="abc",
        header_value="wrong",
    )
    # No secret configured: function allows (caller may still require header in route)
    assert verify_apple_messages_webhook_secret(
        configured_secret="",
        header_value="",
    )
    assert not verify_apple_messages_webhook_secret(
        configured_secret="x",
        header_value="",
    )


def test_permission_text_uses_email_links(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        api_base_url="https://api.example.com",
        api_v1_prefix="/api/v1",
        email_webhook_secret="sec",
    )

    def _gs() -> SimpleNamespace:
        return s

    monkeypatch.setattr("app.services.channel_gateway.email_links.get_settings", _gs)
    t = format_email_permission_text(3, "am_" + "ab" * 16)
    assert "email-approve" in t


def _session_local_for(db: Session):
    def _factory() -> Session:
        return db

    return _factory


def _am_bind(monkeypatch: pytest.MonkeyPatch, *, webhook_secret: str = "whsec") -> None:
    s = SimpleNamespace(
        apple_messages_provider_url="https://provider.example/v1/send",
        apple_messages_access_token="tok",
        apple_messages_business_id="biz",
        apple_messages_webhook_secret=webhook_secret,
        api_base_url="http://testserver",
        api_v1_prefix="/api/v1",
        email_webhook_secret="esec",
    )

    def _gs() -> SimpleNamespace:
        return s

    monkeypatch.setattr("app.core.config.get_settings", _gs)
    monkeypatch.setattr("app.api.routes.apple_messages.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.apple_messages_send.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.email_links.get_settings", _gs)


@patch("app.api.routes.apple_messages.handle_incoming_channel_message")
@patch("app.api.routes.apple_messages.send_apple_message_text")
def test_inbound_json_flow(
    mock_send: MagicMock,
    mock_handle: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mem_db: Session,
) -> None:
    _am_bind(monkeypatch, webhook_secret="")
    monkeypatch.setattr("app.api.routes.apple_messages.SessionLocal", _session_local_for(mem_db))
    mock_handle.return_value = {"message": "Hello", "response_kind": "chat"}
    c = TestClient(app)
    r = c.post(
        "/api/v1/apple-messages/inbound",
        json={
            "provider": "apple_business_messages",
            "customer_id": "customer_1",
            "conversation_id": "conv_a",
            "message_id": "msg_1",
            "text": "ping",
        },
    )
    assert r.status_code == 200
    mock_handle.assert_called_once()
    mock_send.assert_called_once()


@patch("app.api.routes.apple_messages.handle_incoming_channel_message")
@patch("app.api.routes.apple_messages.send_apple_message_text")
def test_inbound_rejects_wrong_secret(
    mock_send: MagicMock,
    mock_handle: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mem_db: Session,
) -> None:
    _am_bind(monkeypatch, webhook_secret="expected_secret")
    monkeypatch.setattr("app.api.routes.apple_messages.SessionLocal", _session_local_for(mem_db))
    c = TestClient(app)
    r = c.post(
        "/api/v1/apple-messages/inbound",
        json={"customer_id": "c", "text": "x"},
        headers={"X-Apple-Messages-Webhook-Secret": "nope"},
    )
    assert r.status_code == 403
    mock_handle.assert_not_called()


@patch("app.api.routes.apple_messages.handle_incoming_channel_message")
@patch("app.api.routes.apple_messages.send_apple_message_text")
def test_inbound_accepts_matching_secret(
    mock_send: MagicMock,
    mock_handle: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mem_db: Session,
) -> None:
    _am_bind(monkeypatch, webhook_secret="expected_secret")
    monkeypatch.setattr("app.api.routes.apple_messages.SessionLocal", _session_local_for(mem_db))
    mock_handle.return_value = {"message": "ok", "response_kind": "chat"}
    c = TestClient(app)
    r = c.post(
        "/api/v1/apple-messages/inbound",
        json={"customer_id": "c2", "text": "y"},
        headers={"X-Apple-Messages-Webhook-Secret": "expected_secret"},
    )
    assert r.status_code == 200
    mock_handle.assert_called_once()


def test_channel_status_am_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        api_base_url="https://am.example",
        api_v1_prefix="/api/v1",
        telegram_bot_token="t",
        slack_bot_token="s",
        slack_signing_secret="sig",
        smtp_host="smtp",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        email_from="e@x.com",
        email_webhook_secret="w",
        whatsapp_access_token="wa",
        whatsapp_phone_number_id="p",
        whatsapp_verify_token="v",
        whatsapp_app_secret="",
        twilio_account_sid="AC",
        twilio_auth_token="t",
        twilio_from_number="+1",
        apple_messages_provider_url="https://p.example/api",
        apple_messages_access_token="at",
        apple_messages_business_id="bid",
        apple_messages_webhook_secret="wh",
    )
    monkeypatch.setattr("app.services.channel_gateway.status.get_settings", lambda: s)
    rows = {r["channel"]: r for r in build_channel_status_list()}
    am = rows["apple_messages"]
    assert am["health"] == "ok"
    assert am["webhook_urls"]["inbound"] == "https://am.example/api/v1/apple-messages/inbound"


def test_channel_status_am_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        api_base_url="",
        api_v1_prefix="/api/v1",
        telegram_bot_token="t",
        slack_bot_token="s",
        slack_signing_secret="sig",
        smtp_host="smtp",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        email_from="e@x.com",
        email_webhook_secret="w",
        whatsapp_access_token="wa",
        whatsapp_phone_number_id="p",
        whatsapp_verify_token="v",
        whatsapp_app_secret="",
        twilio_account_sid="",
        twilio_auth_token="",
        twilio_from_number="",
        apple_messages_provider_url="",
        apple_messages_access_token="",
        apple_messages_business_id="",
        apple_messages_webhook_secret="",
    )
    monkeypatch.setattr("app.services.channel_gateway.status.get_settings", lambda: s)
    rows = {r["channel"]: r for r in build_channel_status_list()}
    am = rows["apple_messages"]
    assert am["health"] == "missing_config"
    assert "APPLE_MESSAGES_PROVIDER_URL" in am["missing"]

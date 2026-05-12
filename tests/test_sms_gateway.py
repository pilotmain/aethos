# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 10: SMS (Twilio) adapter, webhook, signature verify, outbound, audit, status."""

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
from app.services.channel_gateway.email_links import format_email_permission_text
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.sms_adapter import (
    SMSAdapter,
    normalize_twilio_e164,
    sms_default_user_id,
    twilio_form_to_raw_event,
)
from app.services.channel_gateway.sms_verify import twilio_request_signature, verify_twilio_signature
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


def test_phone_normalization_e164() -> None:
    assert normalize_twilio_e164("+1 (555) 123-4567") == "+15551234567"
    assert normalize_twilio_e164("15551234567") == "+15551234567"


def test_sms_default_user_id_and_web_validation() -> None:
    uid = sms_default_user_id("+15551234567")
    assert uid == "sms_15551234567"
    assert validate_web_user_id(uid) == uid
    assert not uid.startswith("wa_")


def test_twilio_form_to_raw_event() -> None:
    form = {
        "From": "+15551234567",
        "To": "+15557654321",
        "Body": "hello",
        "MessageSid": "SMaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "AccountSid": "ACbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    }
    raw = twilio_form_to_raw_event(form)
    assert raw["From"] == "+15551234567"
    assert raw["Body"] == "hello"
    assert raw["MessageSid"].startswith("SM")
    assert raw["provider"] == "twilio"


def test_channel_user_create_and_reuse(mem_db: Session) -> None:
    adapter = SMSAdapter()
    raw = {
        "From": "+15559876543",
        "To": "+15550001111",
        "Body": "ping",
        "MessageSid": "SMxyz",
    }
    u1 = adapter.resolve_app_user_id(mem_db, raw)
    u2 = adapter.resolve_app_user_id(mem_db, raw)
    assert u1 == u2 == "sms_15559876543"
    row = mem_db.scalar(
        select(ChannelUser).where(
            ChannelUser.channel == "sms",
            ChannelUser.channel_user_id == "+15559876543",
        )
    )
    assert row is not None
    assert row.user_id == u1


def test_adapter_normalize_payload(mem_db: Session) -> None:
    adapter = SMSAdapter()
    raw = {
        "From": "+15551112222",
        "To": "+15553334444",
        "Body": " stock check ",
        "MessageSid": "SMsid001",
        "provider": "twilio",
    }
    uid = adapter.resolve_app_user_id(mem_db, raw)
    n = adapter.normalize_message(raw, app_user_id=uid)
    assert n["channel"] == "sms"
    assert n["channel_user_id"] == "+15551112222"
    assert n["user_id"] == uid
    assert n["message"] == "stock check"
    assert n["attachments"] == []
    meta = n["metadata"]
    assert meta["sms_from"] == "+15551112222"
    assert meta["sms_to"] == "+15553334444"
    assert meta["channel_chat_id"] == "+15553334444"
    assert meta["channel_message_id"] == "SMsid001"
    assert meta["provider"] == "twilio"


@patch("app.services.channel_gateway.router.check_channel_governance", return_value=None)
@patch("app.services.web_chat_service.process_web_message")
def test_router_sms_to_core(mock_core: MagicMock, _mock_gov: MagicMock, mem_db: Session) -> None:
    mock_core.return_value = WebChatResult(reply="ack", intent="chat", agent_key="nexa")
    norm = {
        "channel": "sms",
        "channel_user_id": "+15550009999",
        "user_id": "sms_15550009999",
        "message": "ping",
        "attachments": [],
        "metadata": {
            "channel_message_id": "SMm1",
            "channel_chat_id": "+15557654321",
            "channel_thread_id": None,
            "web_session_id": "sms:15550009999",
        },
    }
    out = handle_incoming_channel_message(mem_db, normalized_message=norm)
    assert mock_core.called
    assert out["metadata"]["channel"] == "sms"
    assert out["metadata"]["channel_user_id"] == "+15550009999"


def test_audit_sms_origin(mem_db: Session) -> None:
    norm = {
        "channel": "sms",
        "channel_user_id": "+15551230001",
        "user_id": "sms_15551230001",
        "message": "m",
        "attachments": [],
        "metadata": {
            "channel_message_id": "SMaudit1",
            "channel_chat_id": "+15557650000",
            "channel_thread_id": None,
        },
    }
    with bind_channel_origin(build_channel_origin(norm)):
        audit(mem_db, event_type="test.sms", actor="t", user_id="sms_15551230001", message="x", metadata={})
    row = mem_db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    assert row is not None
    md = dict(row.metadata_json or {})
    assert md.get("channel") == "sms"
    assert md.get("channel_user_id") == "+15551230001"
    assert md.get("channel_message_id") == "SMaudit1"
    assert md.get("channel_chat_id") == "+15557650000"


def test_twilio_signature_valid_and_invalid() -> None:
    url = "https://example.com/api/v1/sms/inbound"
    params = {"Body": "hi", "From": "+15551110000"}
    token = "auth_token_value"
    sig = twilio_request_signature(url=url, post_params=params, auth_token=token)
    assert verify_twilio_signature(
        url=url,
        post_params=params,
        auth_token=token,
        x_twilio_signature=sig,
    )
    assert not verify_twilio_signature(
        url=url,
        post_params=params,
        auth_token=token,
        x_twilio_signature="bogus",
    )
    assert not verify_twilio_signature(
        url="https://wrong/url",
        post_params=params,
        auth_token=token,
        x_twilio_signature=sig,
    )


def test_permission_link_body_includes_approve_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        api_base_url="https://api.example.com",
        api_v1_prefix="/api/v1",
        email_webhook_secret="shared_hmac_secret",
    )

    def _gs() -> SimpleNamespace:
        return s

    monkeypatch.setattr("app.services.channel_gateway.email_links.get_settings", _gs)
    txt = format_email_permission_text(12, "sms_15551234567")
    assert "email-approve" in txt
    assert "email-deny" in txt
    assert "Allow once" in txt or "once" in txt.lower()


def _session_local_for(db: Session):
    def _factory() -> Session:
        return db

    return _factory


def _twilio_sig(url: str, form: dict[str, str], token: str) -> str:
    return twilio_request_signature(url=url, post_params=form, auth_token=token)


def _sms_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    twilio_account_sid: str = "ACtest",
    twilio_auth_token: str = "tok",
    twilio_from_number: str = "+15550001111",
    email_secret: str = "whsec",
) -> None:
    s = SimpleNamespace(
        twilio_account_sid=twilio_account_sid,
        twilio_auth_token=twilio_auth_token,
        twilio_from_number=twilio_from_number,
        api_base_url="http://testserver",
        api_v1_prefix="/api/v1",
        email_webhook_secret=email_secret,
    )

    def _gs() -> SimpleNamespace:
        return s

    monkeypatch.setattr("app.core.config.get_settings", _gs)
    monkeypatch.setattr("app.api.routes.sms.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.sms_send.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.email_links.get_settings", _gs)


@patch("app.api.routes.sms.handle_incoming_channel_message")
@patch("app.api.routes.sms.send_sms_text")
def test_sms_inbound_form_flow(
    mock_send: MagicMock,
    mock_handle: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mem_db: Session,
) -> None:
    _sms_settings(monkeypatch)
    monkeypatch.setattr("app.api.routes.sms.SessionLocal", _session_local_for(mem_db))
    mock_handle.return_value = {"message": "Hello SMS", "response_kind": "chat"}
    c = TestClient(app)
    form = {
        "From": "+15559888777",
        "To": "+15550001111",
        "Body": "ping",
        "MessageSid": "SMtwilio123",
    }
    url = "http://testserver/api/v1/sms/inbound"
    sig = _twilio_sig(url, {k: str(v) for k, v in form.items()}, "tok")
    r = c.post(
        "/api/v1/sms/inbound",
        data=form,
        headers={"X-Twilio-Signature": sig},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True
    mock_handle.assert_called_once()
    mock_send.assert_called_once()
    assert "+15559888777" in str(mock_send.call_args)


@patch("app.api.routes.sms.handle_incoming_channel_message")
@patch("app.api.routes.sms.send_sms_text")
def test_sms_inbound_permission_appends_links(
    mock_send: MagicMock,
    mock_handle: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mem_db: Session,
) -> None:
    _sms_settings(monkeypatch)
    monkeypatch.setattr("app.api.routes.sms.SessionLocal", _session_local_for(mem_db))
    mock_handle.return_value = {
        "message": "Need ok",
        "permission_required": {"permission_request_id": 55},
        "response_kind": "permission_required",
    }
    c = TestClient(app)
    form = {
        "From": "+15551112233",
        "To": "+15550001111",
        "Body": "run task",
        "MessageSid": "SMperm",
    }
    url = "http://testserver/api/v1/sms/inbound"
    sig = _twilio_sig(url, {k: str(v) for k, v in form.items()}, "tok")
    r = c.post(
        "/api/v1/sms/inbound",
        data=form,
        headers={"X-Twilio-Signature": sig},
    )
    assert r.status_code == 200
    sent = mock_send.call_args.kwargs.get("body") or ""
    assert "email-approve" in sent
    assert "Need ok" in sent


def test_sms_inbound_rejects_bad_twilio_signature(monkeypatch: pytest.MonkeyPatch, mem_db: Session) -> None:
    _sms_settings(monkeypatch)
    monkeypatch.setattr("app.api.routes.sms.SessionLocal", _session_local_for(mem_db))
    c = TestClient(app)
    r = c.post(
        "/api/v1/sms/inbound",
        data={"From": "+15551110000", "To": "+1", "Body": "x"},
        headers={"X-Twilio-Signature": "not_valid"},
    )
    assert r.status_code == 403


def test_sms_inbound_skips_verify_when_no_token(monkeypatch: pytest.MonkeyPatch, mem_db: Session) -> None:
    _sms_settings(monkeypatch, twilio_auth_token="")
    monkeypatch.setattr("app.api.routes.sms.SessionLocal", _session_local_for(mem_db))
    with patch("app.api.routes.sms.handle_incoming_channel_message") as mock_h:
        mock_h.return_value = {"message": "ok", "response_kind": "chat"}
        with patch("app.api.routes.sms.send_sms_text"):
            c = TestClient(app)
            r = c.post(
                "/api/v1/sms/inbound",
                data={"From": "+15552220000", "Body": "yo"},
                headers={"X-Twilio-Signature": "anything"},
            )
            assert r.status_code == 200
            mock_h.assert_called_once()


def test_channel_status_sms_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        api_base_url="https://x.example",
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
        twilio_account_sid="ACx",
        twilio_auth_token="sec",
        twilio_from_number="+10000000000",
        apple_messages_provider_url="https://am.example/api",
        apple_messages_access_token="a",
        apple_messages_business_id="b",
        apple_messages_webhook_secret="w",
    )

    monkeypatch.setattr("app.services.channel_gateway.status.get_settings", lambda: s)
    rows = {r["channel"]: r for r in build_channel_status_list()}
    sms = rows["sms"]
    assert sms["health"] == "ok"
    assert sms["configured"] is True
    assert sms["webhook_urls"]["inbound"] == "https://x.example/api/v1/sms/inbound"


def test_channel_status_sms_missing(monkeypatch: pytest.MonkeyPatch) -> None:
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
    sms = rows["sms"]
    assert sms["health"] == "missing_config"
    assert "TWILIO_ACCOUNT_SID" in sms["missing"]

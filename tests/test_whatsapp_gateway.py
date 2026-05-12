# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 9: WhatsApp channel adapter, webhook, outbound, status, audit."""

from __future__ import annotations

import hashlib
import hmac
import json
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
from app.services.audit_service import audit
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.status import build_channel_status_list
from app.services.channel_gateway.whatsapp_adapter import (
    WhatsAppAdapter,
    extract_whatsapp_inbound_messages,
    whatsapp_default_user_id,
)
from app.services.channel_gateway.whatsapp_verify import verify_meta_webhook_signature
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


def test_whatsapp_default_user_id_and_validation() -> None:
    uid = whatsapp_default_user_id("491234567890")
    assert uid.startswith("wa_")
    assert validate_web_user_id(uid) == uid


def test_extract_meta_payload() -> None:
    body = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "15551234567",
                                    "id": "wamid.x",
                                    "type": "text",
                                    "text": {"body": "hello"},
                                }
                            ],
                            "contacts": [{"wa_id": "15551234567", "profile": {"name": "Ann"}}],
                        }
                    }
                ]
            }
        ],
    }
    msgs = extract_whatsapp_inbound_messages(body)
    assert len(msgs) == 1
    assert msgs[0]["from"] == "15551234567"
    assert msgs[0]["text"] == "hello"
    assert msgs[0]["display_name"] == "Ann"


def test_adapter_normalize_and_identity(mem_db: Session) -> None:
    adapter = WhatsAppAdapter()
    raw = {"from": "15550001111", "text": "ping", "message_id": "mid1"}
    uid = adapter.resolve_app_user_id(mem_db, raw)
    assert uid == "wa_15550001111"
    n = adapter.normalize_message(raw, app_user_id=uid)
    assert n["channel"] == "whatsapp"
    assert n["channel_user_id"] == "15550001111"
    assert n["metadata"]["channel_chat_id"] == "15550001111"
    assert n["metadata"]["web_session_id"].startswith("whatsapp:")


@patch("app.services.channel_gateway.router.check_channel_governance", return_value=None)
@patch("app.services.web_chat_service.process_web_message")
def test_router_whatsapp_to_core(mock_core: MagicMock, _mock_gov: MagicMock, mem_db: Session) -> None:
    mock_core.return_value = WebChatResult(reply="ok", intent="chat", agent_key="nexa")
    norm = {
        "channel": "whatsapp",
        "channel_user_id": "1555",
        "user_id": "wa_15550001111",
        "message": "hi",
        "attachments": [],
        "metadata": {
            "channel_message_id": "m1",
            "channel_chat_id": "1555",
            "web_session_id": "whatsapp:1555",
        },
    }
    out = handle_incoming_channel_message(mem_db, normalized_message=norm)
    assert mock_core.called
    assert out["metadata"]["channel"] == "whatsapp"


def test_audit_whatsapp_origin(mem_db: Session) -> None:
    norm = {
        "channel": "whatsapp",
        "channel_user_id": "1555",
        "user_id": "wa_15550001111",
        "message": "x",
        "attachments": [],
        "metadata": {"channel_message_id": "1", "channel_chat_id": "1555"},
    }
    with bind_channel_origin(build_channel_origin(norm)):
        audit(mem_db, event_type="test.wa", actor="t", user_id="wa_15550001111", message="m", metadata={})
    row = mem_db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    assert row is not None
    md = dict(row.metadata_json or {})
    assert md.get("channel") == "whatsapp"
    assert md.get("channel_user_id") == "1555"


def test_signature_verify_roundtrip() -> None:
    secret = "appsecret"
    body = b'{"x":1}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_meta_webhook_signature(app_secret=secret, raw_body=body, x_hub_signature_256=sig)
    assert not verify_meta_webhook_signature(app_secret="wrong", raw_body=body, x_hub_signature_256=sig)


@patch("app.api.routes.whatsapp.send_whatsapp_text")
def test_whatsapp_webhook_post_flow(
    mock_send: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mem_db: Session,
) -> None:
    s = SimpleNamespace(
        whatsapp_access_token="tok",
        whatsapp_phone_number_id="pid",
        whatsapp_verify_token="v",
        whatsapp_app_secret="",
        email_webhook_secret="esec",
        api_base_url="https://ex.com",
        api_v1_prefix="/api/v1",
    )

    def _gs():
        return s

    monkeypatch.setattr("app.api.routes.whatsapp.get_settings", _gs)
    monkeypatch.setattr("app.core.config.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.email_links.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.whatsapp_send.get_settings", _gs)
    monkeypatch.setattr("app.api.routes.whatsapp.SessionLocal", lambda: mem_db)

    with patch(
        "app.api.routes.whatsapp.handle_incoming_channel_message",
        return_value={"message": "yo", "permission_required": None},
    ):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "15559999999",
                                        "id": "w",
                                        "type": "text",
                                        "text": {"body": "hi"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ],
        }
        c = TestClient(app)
        r = c.post("/api/v1/whatsapp/webhook", content=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    mock_send.assert_called_once()


def test_get_verify_challenge(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(whatsapp_verify_token="mytoken")

    def _gs():
        return s

    monkeypatch.setattr("app.api.routes.whatsapp.get_settings", _gs)
    c = TestClient(app)
    r = c.get(
        "/api/v1/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "mytoken", "hub.challenge": "999"},
    )
    assert r.status_code == 200
    assert r.text == "999"


def test_status_whatsapp_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.status.get_settings",
        lambda: SimpleNamespace(
            api_base_url="https://x.com",
            api_v1_prefix="/api/v1",
            telegram_bot_token="t",
            slack_bot_token="s",
            slack_signing_secret="z",
            email_webhook_secret="e",
            smtp_host="h",
            email_from="a@b.com",
            smtp_user="",
            smtp_password="",
            whatsapp_access_token="",
            whatsapp_phone_number_id="",
            whatsapp_verify_token="",
            whatsapp_app_secret="",
            twilio_account_sid="",
            twilio_auth_token="",
            twilio_from_number="",
            apple_messages_provider_url="",
            apple_messages_access_token="",
            apple_messages_business_id="",
            apple_messages_webhook_secret="",
        ),
    )
    rows = {r["channel"]: r for r in build_channel_status_list()}
    w = rows["whatsapp"]
    assert w["health"] == "missing_config"
    assert "WHATSAPP_ACCESS_TOKEN" in w["missing"]
    assert "/whatsapp/webhook" in (w.get("webhook_urls") or {}).get("webhook", "")


def test_permission_links_appended_use_email_helper(monkeypatch: pytest.MonkeyPatch, mem_db: Session) -> None:
    s = SimpleNamespace(
        whatsapp_access_token="tok",
        whatsapp_phone_number_id="pid",
        whatsapp_verify_token="v",
        whatsapp_app_secret="",
        email_webhook_secret="permsecret",
        api_base_url="https://api.example.com",
        api_v1_prefix="/api/v1",
    )

    def _gs():
        return s

    monkeypatch.setattr("app.api.routes.whatsapp.get_settings", _gs)
    monkeypatch.setattr("app.core.config.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.email_links.get_settings", _gs)
    monkeypatch.setattr("app.services.channel_gateway.whatsapp_send.get_settings", _gs)
    monkeypatch.setattr("app.api.routes.whatsapp.SessionLocal", lambda: mem_db)

    with patch(
        "app.api.routes.whatsapp.handle_incoming_channel_message",
        return_value={
            "message": "need perm",
            "permission_required": {"permission_request_id": 77},
        },
    ):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"messages": [{"from": "15551111111", "id": "x", "type": "text", "text": {"body": "run"}}]}}]}],
        }
        mock_send = MagicMock()
        with patch("app.api.routes.whatsapp.send_whatsapp_text", mock_send):
            c = TestClient(app)
            r = c.post("/api/v1/whatsapp/webhook", content=json.dumps(payload), headers={"Content-Type": "application/json"})
        assert r.status_code == 200
        body = str(mock_send.call_args.kwargs.get("body") or "")
        assert "email-approve" in body or "permissions/requests/77" in body

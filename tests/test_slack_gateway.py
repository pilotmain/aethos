# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 6: Slack channel adapter, router, signature, permission interactions."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
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
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin, get_channel_origin
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.slack_adapter import SlackAdapter, slack_default_app_user_id
from app.services.channel_gateway.slack_verify import verify_slack_signature
from app.services.web_chat_service import WebChatResult


def _sign_slack_body(body: bytes, secret: str, ts: str) -> str:
    basestring = b"v0:" + ts.encode() + b":" + body
    return "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()


@pytest.fixture
def mem_db() -> Session:
    # StaticPool + check_same_thread: TestClient runs the app in a worker thread; default
    # :memory: sqlite is not shared across connections/threads.
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


def test_slack_default_user_id_distinct_from_telegram() -> None:
    assert slack_default_app_user_id("U123") == "slack_U123"
    assert not slack_default_app_user_id("U123").startswith("tg_")


def test_slack_adapter_normalize_message_shape() -> None:
    adapter = SlackAdapter()
    raw = {
        "event": {
            "type": "message",
            "user": "U123",
            "text": "hello <@U999>",
            "channel": "C456",
            "ts": "1234.56",
        },
        "team_id": "T01",
    }
    n = adapter.normalize_message(raw, app_user_id="slack_U123")
    assert n["channel"] == "slack"
    assert n["channel_user_id"] == "U123"
    assert n["user_id"] == "slack_U123"
    assert n["message"] == "hello"
    assert n["attachments"] == []
    assert n["metadata"]["channel_message_id"] == "1234.56"
    assert n["metadata"]["channel_chat_id"] == "C456"
    assert n["metadata"]["channel_thread_id"] is None
    assert n["metadata"]["web_session_id"] == "slack:T01:C456"
    assert n["metadata"]["slack_team_id"] == "T01"


def test_slack_adapter_resolve_app_user_id(mem_db: Session) -> None:
    adapter = SlackAdapter()
    raw = {
        "event": {
            "type": "message",
            "user": "U777",
            "text": "hi",
            "channel": "C1",
            "ts": "1.0",
        },
        "team_id": "T9",
    }
    uid = adapter.resolve_app_user_id(mem_db, raw)
    assert uid == "slack_U777"
    row = mem_db.scalar(
        select(ChannelUser).where(
            ChannelUser.channel == "slack",
            ChannelUser.channel_user_id == "U777",
        )
    )
    assert row is not None
    assert row.user_id == "slack_U777"


@patch("app.services.channel_gateway.router.check_channel_governance", return_value=None)
@patch("app.services.web_chat_service.process_web_message")
def test_router_slack_flow_calls_core(mock_core: MagicMock, _mock_gov: MagicMock, mem_db: Session) -> None:
    seen_origin: dict = {}

    def _slack_capture(db, uid, text, **kw):
        seen_origin.update(dict(get_channel_origin() or {}))
        return WebChatResult(reply="ok", intent="chat", agent_key="nexa")

    mock_core.side_effect = _slack_capture
    norm = {
        "channel": "slack",
        "channel_user_id": "U1",
        "user_id": "slack_U1",
        "message": "ping",
        "attachments": [],
        "metadata": {
            "channel_message_id": "9",
            "channel_chat_id": "C9",
            "channel_thread_id": None,
            "web_session_id": "slack:T:C9",
            "slack_team_id": "T",
        },
    }
    out = handle_incoming_channel_message(mem_db, normalized_message=norm)
    assert mock_core.called
    call = mock_core.call_args
    assert call.args[1] == "slack_U1"
    assert call.args[2] == "ping"
    assert call.kwargs.get("web_session_id") == "slack:T:C9"
    assert seen_origin.get("channel") == "slack"
    assert seen_origin.get("channel_user_id") == "U1"
    assert seen_origin.get("slack_team_id") == "T"
    assert out["metadata"]["channel"] == "slack"
    assert out["metadata"]["channel_user_id"] == "U1"


def test_slack_build_channel_origin_audit_fields() -> None:
    n = {
        "channel": "slack",
        "channel_user_id": "U9",
        "metadata": {
            "channel_message_id": "m1",
            "channel_chat_id": "C1",
            "channel_thread_id": None,
            "web_session_id": "slack:T:C",
            "slack_team_id": "T",
        },
    }
    o = build_channel_origin(n)
    assert o["channel"] == "slack"
    assert o["channel_user_id"] == "U9"
    assert o["slack_team_id"] == "T"


def test_audit_metadata_slack_origin(mem_db: Session) -> None:
    from app.services.audit_service import audit

    norm = {
        "channel": "slack",
        "channel_user_id": "U55",
        "user_id": "slack_U55",
        "message": "x",
        "attachments": [],
        "metadata": {
            "channel_message_id": "1",
            "channel_chat_id": "C",
            "web_session_id": "slack:T:C",
        },
    }
    origin = build_channel_origin(norm)
    with bind_channel_origin(origin):
        audit(
            mem_db,
            event_type="test.slack.lineage",
            actor="t",
            user_id="slack_U55",
            message="m",
            metadata={"k": 2},
        )
    row = mem_db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    assert row is not None
    md = dict(row.metadata_json or {})
    assert md.get("channel") == "slack"
    assert md.get("channel_user_id") == "U55"


def test_verify_slack_signature_rejects_bad_sig() -> None:
    body = b'{"x":1}'
    ts = str(int(time.time()))
    ok = verify_slack_signature(
        signing_secret="sec",
        request_timestamp=ts,
        raw_body=body,
        slack_signature="v0=deadbeef",
    )
    assert ok is False


def test_verify_slack_signature_accepts_valid() -> None:
    secret = "test_slack_signing"
    body = b'{"type":"url_verification","challenge":"abc"}'
    ts = str(int(time.time()))
    sig = _sign_slack_body(body, secret, ts)
    assert verify_slack_signature(
        signing_secret=secret,
        request_timestamp=ts,
        raw_body=body,
        slack_signature=sig,
    )


def _settings_slack(monkeypatch: pytest.MonkeyPatch, secret: str, token: str = "xoxb-test") -> None:
    s = SimpleNamespace(
        slack_bot_token=token,
        slack_signing_secret=secret,
        api_v1_prefix="/api/v1",
    )

    def _gs():
        return s

    monkeypatch.setattr("app.api.routes.slack.get_settings", _gs)
    monkeypatch.setattr("app.core.config.get_settings", _gs)


def _session_local_for(db: Session):
    def _factory() -> Session:
        return db

    return _factory


@patch("app.api.routes.slack.slack_chat_post_message")
@patch("app.api.routes.slack.handle_incoming_channel_message")
def test_slack_events_http_routes_through_gateway(
    mock_handle: MagicMock,
    mock_post: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mem_db: Session,
) -> None:
    secret = "evt_secret_xyz"
    _settings_slack(monkeypatch, secret)
    monkeypatch.setattr("app.api.routes.slack.SessionLocal", _session_local_for(mem_db))

    mock_handle.return_value = {"message": "reply text", "permission_required": None}

    body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "message",
                "user": "U42",
                "text": "hello",
                "channel": "C99",
                "ts": "111.222",
            },
        }
    ).encode()
    ts = str(int(time.time()))
    c = TestClient(app)
    r = c.post(
        "/api/v1/slack/events",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": _sign_slack_body(body, secret, ts),
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True
    mock_handle.assert_called_once()
    norm = mock_handle.call_args.kwargs.get("normalized_message")
    assert norm["channel"] == "slack"
    assert norm["channel_user_id"] == "U42"
    mock_post.assert_called_once()


def test_slack_events_invalid_signature_401(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "good_secret"
    _settings_slack(monkeypatch, secret)
    body = b'{"type":"url_verification","challenge":"x"}'
    ts = str(int(time.time()))
    c = TestClient(app)
    r = c.post(
        "/api/v1/slack/events",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": "v0=deadbeef",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 401


def test_slack_url_verification_challenge(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "url_sec"
    _settings_slack(monkeypatch, secret)
    body = json.dumps({"type": "url_verification", "challenge": "abc123"}).encode()
    ts = str(int(time.time()))
    c = TestClient(app)
    r = c.post(
        "/api/v1/slack/events",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": _sign_slack_body(body, secret, ts),
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 200
    assert r.json() == {"challenge": "abc123"}


@patch("app.api.routes.slack.ap_grant_permission")
@patch("app.api.routes.slack.resume_host_executor_after_grant")
@patch("app.api.routes.slack._post_response_url")
def test_slack_interaction_grant_once_flow(
    mock_post_url: MagicMock,
    mock_resume: MagicMock,
    mock_grant: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mem_db: Session,
) -> None:
    secret = "int_secret"
    _settings_slack(monkeypatch, secret)
    monkeypatch.setattr("app.api.routes.slack.SessionLocal", _session_local_for(mem_db))

    mem_db.add(
        ChannelUser(
            channel="slack",
            channel_user_id="U88",
            user_id="slack_U88",
        )
    )
    mem_db.commit()

    mock_grant.return_value = SimpleNamespace(id=1)

    payload = {
        "type": "block_actions",
        "user": {"id": "U88"},
        "response_url": "https://hooks.slack.com/actions/x",
        "actions": [
            {
                "value": json.dumps({"permission_id": 42, "action": "approve_once"}),
            }
        ],
    }
    body = urlencode({"payload": json.dumps(payload)}).encode()
    ts = str(int(time.time()))
    c = TestClient(app)
    r = c.post(
        "/api/v1/slack/interactions",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": _sign_slack_body(body, secret, ts),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert r.status_code == 200
    mock_grant.assert_called_once()
    mock_resume.assert_called_once()
    mock_post_url.assert_called()


def test_permission_blocks_encode_permission_id() -> None:
    from app.services.channel_gateway.slack_blocks import permission_blocks

    blocks = permission_blocks(
        pr={"permission_request_id": 7, "scope": "s", "target": "t"},
        channel_for_reply="C",
    )
    actions = blocks[1]["elements"]
    v0 = json.loads(actions[0]["value"])
    assert v0["permission_id"] == 7
    assert v0["action"] == "approve_once"

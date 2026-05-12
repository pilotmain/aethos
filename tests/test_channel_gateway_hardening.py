# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 12: retries, rate limits, normalization validation, health signals, audit hooks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.models.audit_log import AuditLog
from app.services.channel_gateway.gateway_events import (
    audit_outbound_failure,
    get_health_details,
    record_outbound_failure,
    record_outbound_success,
    reset_health_for_tests,
)
from app.services.channel_gateway.normalized_message import validate_normalized_message
import app.services.channel_gateway.rate_limit as rate_limit_mod
from app.services.channel_gateway.rate_limit import (
    GatewayRateLimitExceeded,
    acquire_outbound_slot,
    reset_limits_for_tests,
)
from app.services.channel_gateway.retry import outbound_with_retry
from app.services.channel_gateway.status import build_channel_status_list


@pytest.fixture(autouse=True)
def _reset_gateway_infra() -> None:
    reset_limits_for_tests()
    reset_health_for_tests()
    yield
    reset_limits_for_tests()
    reset_health_for_tests()


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


def test_outbound_retry_then_success() -> None:
    n = {"attempts": 0}

    def flaky() -> str:
        n["attempts"] += 1
        if n["attempts"] < 3:
            raise RuntimeError("transient")
        return "ok"

    with patch("app.services.channel_gateway.retry.time.sleep"):
        out = outbound_with_retry(channel="sms", operation="test", func=flaky, max_attempts=3)
    assert out == "ok"
    assert n["attempts"] == 3


def test_rate_limit_user_burst(monkeypatch: pytest.MonkeyPatch) -> None:
    # Relax channel-wide pacing so this test exercises only the per-user burst window.
    monkeypatch.setitem(rate_limit_mod.CHANNEL_MIN_INTERVAL_SEC, "slack", 0.0)
    uid = "tg_123456789"
    for _ in range(60):
        acquire_outbound_slot(channel="slack", user_id=uid)
    with pytest.raises(GatewayRateLimitExceeded):
        acquire_outbound_slot(channel="slack", user_id=uid)


def test_rate_limit_channels_independent() -> None:
    acquire_outbound_slot(channel="slack", user_id="u1")
    acquire_outbound_slot(channel="sms", user_id="u1")


def test_validate_normalized_message_rejects_bad() -> None:
    with pytest.raises(ValueError):
        validate_normalized_message({})  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        validate_normalized_message(
            {"channel": "x", "channel_user_id": "", "user_id": "tg_1"}
        )


def test_validate_normalized_message_ok() -> None:
    validate_normalized_message(
        {
            "channel": "web",
            "channel_user_id": "u",
            "user_id": "web_x",
            "message": "hi",
            "attachments": [],
            "metadata": {},
        }
    )


def test_health_details_surface_in_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    record_outbound_success("sms")
    record_outbound_failure("email", "smtp down")
    s = SimpleNamespace(
        api_base_url="https://x.example.com",
        api_v1_prefix="/api/v1",
        telegram_bot_token="t",
        slack_bot_token="s",
        slack_signing_secret="z",
        smtp_host="smtp",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        email_from="a@b.com",
        email_webhook_secret="e",
        whatsapp_access_token="wa",
        whatsapp_phone_number_id="p",
        whatsapp_verify_token="v",
        whatsapp_app_secret="",
        twilio_account_sid="AC",
        twilio_auth_token="tok",
        twilio_from_number="+1",
        apple_messages_provider_url="http://p",
        apple_messages_access_token="t",
        apple_messages_business_id="b",
        apple_messages_webhook_secret="w",
    )
    monkeypatch.setattr("app.services.channel_gateway.status.get_settings", lambda: s)
    rows = {r["channel"]: r for r in build_channel_status_list()}
    assert rows["sms"].get("health_details", {}).get("last_success")
    assert rows["email"].get("health_details", {}).get("last_error")


def test_audit_outbound_failure_writes_row(mem_db: Session) -> None:
    audit_outbound_failure(
        mem_db,
        channel="sms",
        user_id="sms_15551234567",
        message="boom",
        metadata={"stage": "outbound"},
    )
    row = mem_db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    assert row is not None
    assert row.event_type == "gateway.outbound_failed"
    md = dict(row.metadata_json or {})
    assert md.get("channel") == "sms"


def test_get_health_details_roundtrip() -> None:
    reset_health_for_tests()
    record_outbound_failure("whatsapp", "api")
    d = get_health_details("whatsapp")
    assert d is not None
    assert "last_error" in d

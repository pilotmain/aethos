"""Phase 8: GET /api/v1/channels/status — env presence only, no secrets."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.channel_gateway.status import build_channel_status_list


def _settings(**kwargs: object) -> SimpleNamespace:
    base = dict(
        api_base_url="https://api.example.com",
        api_v1_prefix="/api/v1",
        telegram_bot_token="x",
        slack_bot_token="s",
        slack_signing_secret="sig",
        smtp_host="smtp",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        email_from="nexa@example.com",
        email_webhook_secret="wh",
        whatsapp_access_token="wat",
        whatsapp_phone_number_id="pnid",
        whatsapp_verify_token="wvt",
        whatsapp_app_secret="",
        twilio_account_sid="ACtest",
        twilio_auth_token="twilio_secret",
        twilio_from_number="+15550001111",
        apple_messages_provider_url="https://provider.example/msg",
        apple_messages_access_token="am_tok",
        apple_messages_business_id="biz_id",
        apple_messages_webhook_secret="am_wh",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


@pytest.fixture
def api_client():
    app.dependency_overrides[get_valid_web_user_id] = lambda: "web_opsuser"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_web_always_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.status.get_settings",
        lambda: _settings(),
    )
    rows = {r["channel"]: r for r in build_channel_status_list()}
    w = rows["web"]
    assert w["configured"] is True
    assert w["enabled"] is True
    assert w["health"] == "ok"


def test_slack_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.status.get_settings",
        lambda: _settings(slack_bot_token="", slack_signing_secret=""),
    )
    rows = {r["channel"]: r for r in build_channel_status_list()}
    s = rows["slack"]
    assert s["configured"] is False
    assert "SLACK_BOT_TOKEN" in s["missing"]
    assert "SLACK_SIGNING_SECRET" in s["missing"]
    assert s["health"] == "missing_config"


def test_slack_configured_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.status.get_settings",
        lambda: _settings(),
    )
    rows = {r["channel"]: r for r in build_channel_status_list()}
    s = rows["slack"]
    assert s["configured"] is True
    assert s["health"] == "ok"
    assert s["webhook_urls"]["events"] == "https://api.example.com/api/v1/slack/events"


def test_email_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.status.get_settings",
        lambda: _settings(email_webhook_secret="", smtp_host="", email_from=""),
    )
    rows = {r["channel"]: r for r in build_channel_status_list()}
    e = rows["email"]
    assert e["configured"] is False
    assert "EMAIL_WEBHOOK_SECRET" in e["missing"]
    assert "SMTP_HOST" in e["missing"]
    assert "EMAIL_FROM" in e["missing"]


def test_webhook_urls_with_api_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.status.get_settings",
        lambda: _settings(),
    )
    rows = {r["channel"]: r for r in build_channel_status_list()}
    assert rows["email"]["webhook_urls"]["inbound"] == "https://api.example.com/api/v1/email/inbound"
    assert rows["slack"]["webhook_urls"]["interactions"].endswith("/slack/interactions")


def test_api_response_shape_no_secrets(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.status.get_settings",
        lambda: _settings(slack_bot_token="", slack_signing_secret=""),
    )
    r = api_client.get("/api/v1/channels/status")
    assert r.status_code == 200
    body = r.json()
    assert "channels" in body
    text = r.text
    assert "SLACK_BOT_TOKEN" in text  # env name only (missing list)
    assert "xoxb" not in text.lower()
    assert "slack_signing_secret_value" not in text.lower()


def test_api_base_localhost_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_gateway.status.get_settings",
        lambda: _settings(api_base_url="http://localhost:8000"),
    )
    rows = {r["channel"]: r for r in build_channel_status_list()}
    slack_notes = " ".join(rows["slack"]["notes"])
    assert "localhost" in slack_notes.lower() or "local" in slack_notes.lower()

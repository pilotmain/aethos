"""Phase 9 — channels must funnel through NexaGateway."""

from __future__ import annotations

from app.services.channels.router import route_inbound
from app.services.channels.slack_channel import SlackChannel
from app.services.channels.telegram_channel import TelegramChannel
from app.services.channels.web_channel import WebChannel


def test_route_inbound_returns_chat_when_no_mission(monkeypatch):
    monkeypatch.setattr(
        "app.services.gateway.runtime.NexaGateway.handle_message",
        lambda self, text, user_id, **kw: {"mode": "chat", "text": "No mission detected"},
    )
    out = route_inbound("hello there", "u1", channel="web")
    assert out.get("mode") == "chat"


def test_web_channel_receive_delegates(monkeypatch):
    calls: list[tuple[str, str]] = []

    def capture(self, text, user_id, **kwargs):
        calls.append((text, user_id))
        return {"mode": "chat", "text": "No mission detected"}

    monkeypatch.setattr(
        "app.services.gateway.runtime.NexaGateway.handle_message",
        capture,
    )
    ch = WebChannel()
    out = ch.receive({"text": "ping", "user_id": "alice"})
    assert calls == [("ping", "alice")]
    assert out.get("mode") == "chat"


def test_telegram_channel_receive(monkeypatch):
    monkeypatch.setattr(
        "app.services.gateway.runtime.NexaGateway.handle_message",
        lambda self, text, user_id, **kw: {"ok": True, "text": text, "uid": user_id},
    )
    out = TelegramChannel().receive({"text": "hi", "telegram_user_id": "tg99"})
    assert out["uid"] == "tg99"


def test_slack_channel_receive(monkeypatch):
    monkeypatch.setattr(
        "app.services.gateway.runtime.NexaGateway.handle_message",
        lambda self, text, user_id, **kw: {"uid": user_id},
    )
    out = SlackChannel().receive({"text": "yo", "slack_user_id": "U123"})
    assert out["uid"] == "U123"

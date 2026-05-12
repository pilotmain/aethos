# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 9 — channels must funnel through NexaGateway."""

from __future__ import annotations

from app.services.channels.router import route_inbound
from app.services.channels.slack_channel import SlackChannel
from app.services.channels.telegram_channel import TelegramChannel
from app.services.channels.web_channel import WebChannel


def test_route_inbound_returns_chat_when_no_mission(monkeypatch):
    monkeypatch.setattr(
        "app.services.gateway.runtime.NexaGateway.handle_message",
        lambda self, gctx, text, **kw: {"mode": "chat", "text": "No mission detected"},
    )
    out = route_inbound("hello there", "u1", channel="web")
    assert out.get("mode") == "chat"


def test_web_channel_receive_delegates(monkeypatch):
    calls: list[tuple[str, str]] = []

    def capture(self, gctx, text, **kwargs):
        calls.append((text, gctx.user_id))
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
        lambda self, gctx, text, **kw: {"ok": True, "text": text, "uid": gctx.user_id},
    )
    out = TelegramChannel().receive({"text": "hi", "telegram_user_id": "tg99"})
    assert out["uid"] == "tg99"


def test_slack_channel_receive(monkeypatch):
    monkeypatch.setattr(
        "app.services.gateway.runtime.NexaGateway.handle_message",
        lambda self, gctx, text, **kw: {"uid": gctx.user_id},
    )
    out = SlackChannel().receive({"text": "yo", "slack_user_id": "U123"})
    assert out["uid"] == "U123"

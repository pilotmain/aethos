"""Phase 35 — Telegram structured turns first; full chat matches web via gateway."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.channels.telegram_gateway_reply import (
    format_telegram_gateway_reply,
    telegram_gateway_should_hand_off,
)
from app.services.gateway.runtime import NexaGateway


def test_gateway_chat_uses_composed_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.gateway.runtime.NexaGateway.handle_full_chat",
        lambda self, text, user_id, **kw: {
            "mode": "chat",
            "text": "composed-reply",
            "intent": "general_chat",
        },
    )
    gw = NexaGateway().handle_message("hello world tea cozy", "u_test_gateway_compose")
    assert gw.get("mode") == "chat"
    assert gw.get("text") == "composed-reply"


def test_telegram_gateway_hand_off_chat_mode() -> None:
    assert not telegram_gateway_should_hand_off({"mode": "chat", "text": ""})
    assert telegram_gateway_should_hand_off({"mode": "chat", "text": "any reply"})
    assert telegram_gateway_should_hand_off({"mode": "chat", "text": "", "dev_run": {"ok": True}})


def test_format_mission_reply_truncates() -> None:
    body = format_telegram_gateway_reply(
        {"status": "completed", "mission": {"title": "Ship dashboard"}, "result": {"ok": True}}
    )
    assert "Ship dashboard" in body
    assert "completed" in body


def test_telegram_bot_uses_structured_gateway() -> None:
    text = (Path(__file__).resolve().parents[1] / "app" / "bot" / "telegram_bot.py").read_text(
        encoding="utf-8"
    )
    assert "try_structured_turn(" in text
    assert "NexaGateway" in text


@pytest.mark.parametrize(
    ("src", "must_have"),
    [
        ("app/bot/telegram_bot.py", "try_structured_turn"),
        ("app/services/channel_gateway/telegram_adapter.py", "route_telegram_text_through_gateway"),
    ],
)
def test_sources_reference_gateway_funnel(src: str, must_have: str) -> None:
    root = Path(__file__).resolve().parents[1]
    p = root / src
    assert must_have in p.read_text(encoding="utf-8")

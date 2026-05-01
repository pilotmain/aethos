"""Phase 34 — Telegram plain text uses the same gateway admission as web."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.channels.telegram_gateway_reply import (
    format_telegram_gateway_reply,
    telegram_gateway_should_hand_off,
)
from app.services.gateway.runtime import GATEWAY_CHAT_FALLBACK_TEXT, NexaGateway


def test_gateway_fallback_constant_matches_runtime() -> None:
    gw = NexaGateway().handle_message("hello world tea cozy", "u_test_gateway_fallback")
    assert gw.get("mode") == "chat"
    assert gw.get("text") == GATEWAY_CHAT_FALLBACK_TEXT


def test_telegram_gateway_hand_off_chat_vs_fallback() -> None:
    assert not telegram_gateway_should_hand_off({"mode": "chat", "text": GATEWAY_CHAT_FALLBACK_TEXT})
    assert telegram_gateway_should_hand_off({"mode": "chat", "text": "Dev workspaces registered."})
    assert telegram_gateway_should_hand_off({"mode": "chat", "text": "", "dev_run": {"ok": True}})


def test_format_mission_reply_truncates() -> None:
    body = format_telegram_gateway_reply(
        {"status": "completed", "mission": {"title": "Ship dashboard"}, "result": {"ok": True}}
    )
    assert "Ship dashboard" in body
    assert "completed" in body


def test_telegram_bot_imports_route_inbound() -> None:
    text = (Path(__file__).resolve().parents[1] / "app" / "bot" / "telegram_bot.py").read_text(
        encoding="utf-8"
    )
    assert "route_inbound(" in text
    assert "telegram_gateway_should_hand_off" in text


@pytest.mark.parametrize(
    ("src", "must_have"),
    [
        ("app/bot/telegram_bot.py", "route_inbound"),
        ("app/services/channel_gateway/telegram_adapter.py", "route_telegram_text_through_gateway"),
    ],
)
def test_sources_reference_gateway_funnel(src: str, must_have: str) -> None:
    root = Path(__file__).resolve().parents[1]
    p = root / src
    assert must_have in p.read_text(encoding="utf-8")

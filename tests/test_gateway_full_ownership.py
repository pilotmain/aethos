"""Phase 35 — NexaGateway owns generic chat; behavior_engine is not wired from Telegram text paths."""

from __future__ import annotations

import inspect

import pytest

from app.bot import telegram_bot as telegram_bot_module
from app.services.gateway.runtime import NexaGateway


def test_plain_text_handler_avoids_build_response() -> None:
    src = inspect.getsource(telegram_bot_module._handle_incoming_text_impl)
    assert "build_response" not in src


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_handle_message_calls_full_chat_when_no_structured_turn(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
) -> None:
    calls: list[tuple[str, str]] = []

    def track(self: NexaGateway, text: str, user_id: str, **kw: object) -> dict:
        calls.append((text, user_id))
        return {"mode": "chat", "text": f"echo:{text}", "intent": "general_chat"}

    monkeypatch.setattr(NexaGateway, "handle_full_chat", track)
    out = NexaGateway().handle_message("just chatting", "u_phase35", db=db_session)
    assert calls == [("just chatting", "u_phase35")]
    assert out.get("text") == "echo:just chatting"


def test_gateway_full_chat_is_exported_on_runtime_module() -> None:
    assert callable(NexaGateway.handle_full_chat)

"""Phase 43 — gateway chat path attaches ``memory_context`` for composer consumption."""

from __future__ import annotations

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


def test_handle_full_chat_sets_memory_context(db_session, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_compose(self, raw, intent, beh_ctx, **kwargs):
        captured["memory_context"] = beh_ctx.memory.get("memory_context") if beh_ctx.memory else None
        return "composed"

    class StubMI:
        def recent_for_prompt(self, uid: str, max_chars: int = 3500) -> str:
            return "MEMORY_BRAIN_SNIPPET"

    monkeypatch.setattr(NexaGateway, "compose_llm_reply", fake_compose)
    monkeypatch.setattr("app.services.memory.memory_index.MemoryIndex", StubMI)
    monkeypatch.setattr("app.services.intent_classifier.get_intent", lambda *a, **k: "general_chat")
    monkeypatch.setattr("app.services.general_response.looks_like_general_question", lambda t: False)
    monkeypatch.setattr("app.services.telegram_onboarding.is_weak_input", lambda t: False)

    gctx = GatewayContext.from_channel("mem_brain_u1", "web", {})
    out = NexaGateway().handle_full_chat(gctx, "phase43 memory probe text", db=db_session)
    assert out.get("text") == "composed"
    assert captured["memory_context"] == "MEMORY_BRAIN_SNIPPET"


def test_gateway_memory_extra_merged_into_behavior_memory(db_session, monkeypatch) -> None:
    merged: dict[str, object] = {}

    def fake_compose(self, raw, intent, beh_ctx, **kwargs):
        merged.update(dict(beh_ctx.memory or {}))
        return "ok"

    class StubMI:
        def recent_for_prompt(self, uid: str, max_chars: int = 3500) -> str:
            return "ctx"

    monkeypatch.setattr(NexaGateway, "compose_llm_reply", fake_compose)
    monkeypatch.setattr("app.services.memory.memory_index.MemoryIndex", StubMI)
    monkeypatch.setattr("app.services.intent_classifier.get_intent", lambda *a, **k: "general_chat")
    monkeypatch.setattr("app.services.general_response.looks_like_general_question", lambda t: False)
    monkeypatch.setattr("app.services.telegram_onboarding.is_weak_input", lambda t: False)

    gctx = GatewayContext.from_channel("mem_merge_u1", "web", {})
    gctx.memory = {"custom_hint": "from_channel"}
    NexaGateway().handle_full_chat(gctx, "hello merge", db=db_session)
    assert merged.get("memory_context") == "ctx"
    assert merged.get("custom_hint") == "from_channel"

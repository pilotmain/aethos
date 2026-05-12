# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control ``POST …/mission-control/gateway/run`` must spawn NL sub-agents like ``/web/chat``."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_nl_spawn_when_intent_is_general_chat(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    """Classifier may return ``general_chat``; registry NL cues must still run before LLM chat."""
    monkeypatch.setattr(NexaGateway, "_maybe_auto_dev_investigation", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.services.intent_classifier.get_intent",
        lambda *a, **k: "general_chat",
    )
    captured: dict[str, str] = {}

    def fake_spawn(db, uid, text, *, parent_chat_id: str) -> str:
        captured["uid"] = uid
        captured["text"] = text
        captured["parent_chat_id"] = parent_chat_id
        return "✅ NL roster spawn ok."

    monkeypatch.setattr(
        "app.services.sub_agent_natural_creation.try_spawn_natural_sub_agents",
        fake_spawn,
    )

    uid = f"gw_nl_{uuid.uuid4().hex[:12]}"
    ctx = GatewayContext.from_channel(uid, "web", {"via_gateway": True})
    out = NexaGateway().handle_message(ctx, "Create a marketing agent", db=db_session)

    assert out.get("intent") == "create_sub_agent"
    assert "NL roster" in (out.get("text") or "")
    assert captured.get("text") == "Create a marketing agent"
    assert captured.get("uid") == uid

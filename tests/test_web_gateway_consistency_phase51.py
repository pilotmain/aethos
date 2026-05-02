"""Phase 51 — web and gateway agree on action-oriented tone without legacy dev-agent copy."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_stuck_dev_same_core_tone_web_and_telegram(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    monkeypatch.setattr(
        NexaGateway,
        "compose_llm_reply",
        lambda self, *a, **k: "Focused technical guidance.",
    )
    monkeypatch.setattr(
        "app.services.intent_classifier.get_intent",
        lambda *a, **k: "stuck_dev",
    )
    monkeypatch.setattr(
        "app.services.dev_runtime.gateway_hint.maybe_dev_gateway_hint",
        lambda *a, **k: None,
    )

    msg = "docker build fails and pytest errors on CI"
    uid = f"cmp_{uuid.uuid4().hex[:10]}"

    web = NexaGateway().handle_message(
        GatewayContext(user_id=uid, channel="web", extras={"via_gateway": True}),
        msg,
        db=db_session,
    )
    tg = NexaGateway().handle_message(
        GatewayContext(user_id=uid, channel="telegram", extras={"via_gateway": True}),
        msg,
        db=db_session,
    )

    for label, out in (("web", web), ("tg", tg)):
        text = (out.get("text") or "").lower()
        assert "focused technical guidance" in text, label
        assert "development agent" not in text
        assert "tell cursor" not in text
        assert "post /api/" not in text

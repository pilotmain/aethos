"""P0 — retry phrases invoke the retry turn (no idle ‘say retry again’ loop)."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_retry_external_execution_calls_retry_turn(monkeypatch, db_session) -> None:
    calls: list[tuple[str, str]] = []

    def capture(db, uid, raw, cctx):
        calls.append((uid, raw))
        return {
            "text": "### Progress\n\n→ Retrying railway investigation\n→ Starting investigation\n\ndone.",
            "intent": "external_execution_continue",
        }

    monkeypatch.setattr(
        "app.services.external_execution_session.try_retry_external_execution_turn",
        capture,
    )

    uid = f"el_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(gctx, "retry external execution", db=db_session)
    assert len(calls) == 1
    assert calls[0][0] == uid
    text = (out.get("text") or "").lower()
    assert "say retry external execution" not in text
    assert "retrying" in text or "starting investigation" in text

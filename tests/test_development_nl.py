"""Gateway NL development task routing."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.gateway.context import GatewayContext
from app.services.gateway.development_nl import try_development_nl_gateway_turn


def test_development_nl_returns_payload() -> None:
    gctx = GatewayContext(user_id="tg_1", channel="web", extras={"web_session_id": "s"})
    out = try_development_nl_gateway_turn(
        gctx,
        "Development add a delete button to the todo app",
        MagicMock(),
    )
    assert out is not None
    assert out.get("mode") == "chat"
    assert out.get("intent") in ("development_nl_hint", "development_nl_routed")
    assert "delete" in (out.get("text") or "").lower()

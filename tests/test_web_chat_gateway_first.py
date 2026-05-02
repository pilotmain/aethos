"""Web chat uses :meth:`NexaGateway.handle_message` on the main path (Phase 51)."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.next_action_apply import NextActionApplicationResult
from app.services.web_chat_service import process_web_message


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_web_main_path_matches_gateway_for_stuck_dev(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    """Gateway-first web flow receives Phase 50 assist appendix like direct gateway calls."""
    monkeypatch.setattr(
        NexaGateway,
        "compose_llm_reply",
        lambda self, *a, **k: "Concrete troubleshooting steps.",
    )
    monkeypatch.setattr(
        "app.services.intent_classifier.get_intent",
        lambda *a, **k: "stuck_dev",
    )
    monkeypatch.setattr(
        "app.services.dev_runtime.gateway_hint.maybe_dev_gateway_hint",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.next_action_apply.apply_next_action_to_user_text",
        lambda db, cctx, user_text, depth=0, web_session_id=None: NextActionApplicationResult(
            None, user_text, False, False, None
        ),
    )

    uid = f"web_{uuid.uuid4().hex[:12]}"
    msg = "pytest fails on EKS — OIDC token rejected before mongo connects"

    gctx = GatewayContext(
        user_id=uid,
        channel="web",
        extras={"web_session_id": "sess1", "routing_agent_key": "nexa", "via_gateway": True},
    )
    direct = NexaGateway().handle_message(gctx, msg, db=db_session)

    web_out = process_web_message(db_session, uid, msg, web_session_id="sess1")

    assert "Concrete troubleshooting" in (direct.get("text") or "")
    assert "Concrete troubleshooting" in web_out.reply
    assert "Development agent" not in web_out.reply
    assert "tell Cursor" not in web_out.reply.lower()

"""P0 — pasted Railway tokens trigger secure setup instructions (gateway-first)."""

from __future__ import annotations

import json
import uuid

import pytest

from app.services.conversation_context_service import get_or_create_context
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


def test_gateway_railway_api_key_paste_secure_setup(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: __import__("types").SimpleNamespace(
            nexa_operator_mode=False,
            nexa_operator_zero_nag=False,
            nexa_operator_session_credential_reuse=False,
        ),
    )
    uid = f"sec_setup_{uuid.uuid4().hex[:10]}"
    msg = "here is railway api key = abc123secretvalue and i approve"
    out = NexaGateway().handle_message(
        GatewayContext(user_id=uid, channel="web"),
        msg,
        db=db_session,
    )
    body = (out.get("text") or "").lower()
    assert "detected a railway token" in body
    assert ".env" in body
    assert "railway_token" in body.replace(" ", "")
    assert "docker compose restart" in body or "restart" in body
    assert "rotate" in body
    assert "abc123secretvalue" not in body

    cctx = get_or_create_context(db_session, uid)
    blob = json.loads(cctx.current_flow_state_json or "{}")
    hint = blob.get("external_credential_hint") or {}
    assert hint.get("credential_setup_needed") is True
    assert hint.get("service") == "railway"
    assert hint.get("secret_seen_in_chat") is True
    assert "abc123" not in json.dumps(blob)

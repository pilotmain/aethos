# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 — pasted Railway tokens trigger credential setup flow (no echo)."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_railway_api_key_in_chat_points_to_env_restart(monkeypatch, db_session) -> None:
    secret_reply = {
        "mode": "chat",
        "text": (
            "Token seen in chat — add RAILWAY_TOKEN to `.env` on the worker.\n\n"
            "```bash\nRAILWAY_TOKEN=your_token_here\ndocker compose restart api bot\n```"
        ),
        "intent": "credential_setup",
    }
    monkeypatch.setattr(
        "app.services.external_execution_credentials.maybe_handle_external_credential_chat_turn",
        lambda db, user_id, user_text: secret_reply,
    )

    uid = f"el_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(
        gctx,
        "here is railway api key = abc123secret",
        db=db_session,
    )
    body = out.get("text") or ""
    assert "abc123secret" not in body
    assert "RAILWAY_TOKEN" in body
    assert "docker compose restart" in body.lower()

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 37 — GatewayContext is the single carrier through NexaGateway routing."""

from __future__ import annotations

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_same_gateway_context_passes_through_structured_approval_and_chat(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
) -> None:
    """Handlers receive the identical object instance from handle_message."""
    ctx = GatewayContext.from_channel("ctx_prop_u1", "web", {})
    captured: list[int] = []

    def structured(self: NexaGateway, gctx: GatewayContext, text: str, db) -> dict | None:
        captured.append(id(gctx))
        return None

    def approval(self: NexaGateway, gctx: GatewayContext, text: str, db) -> dict | None:
        captured.append(id(gctx))
        return None

    def full_chat(self: NexaGateway, gctx: GatewayContext, text: str, **kw) -> dict:
        captured.append(id(gctx))
        return {"mode": "chat", "text": "done", "intent": "test"}

    monkeypatch.setattr(NexaGateway, "_try_structured_route", structured)
    monkeypatch.setattr(NexaGateway, "_try_approval_route", approval)
    monkeypatch.setattr(NexaGateway, "handle_full_chat", full_chat)

    oid = id(ctx)
    out = NexaGateway().handle_message(ctx, "hello", db=db_session)
    assert captured == [oid, oid, oid]
    assert out.get("text") == "done"


def test_from_channel_maps_legacy_payload_without_raw_metadata_dict_at_boundary() -> None:
    """Permissions/extras replace flat owner flags; callers still pass one payload dict once."""
    g = GatewayContext.from_channel(
        "u",
        "telegram",
        {"telegram_owner": True, "telegram_role": "admin", "telegram_chat_id": "1"},
    )
    assert g.permissions.get("owner") is True
    assert g.permissions.get("telegram_role") == "admin"
    assert g.extras.get("telegram_chat_id") == "1"
    assert g.extras.get("via_gateway") is True

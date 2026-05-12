# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 36 — approvals route through NexaGateway."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.gateway.approval_flow import try_gateway_approval_route
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_handles_approve_job_line_web(db_session) -> None:
    ctx = GatewayContext.from_channel("u_appr_web", "web", {"via_gateway": True})
    out = NexaGateway().handle_message(ctx, "approve job #999999", db=db_session)
    assert out.get("mode") == "chat"
    text = (out.get("text") or "").lower()
    assert "not found" in text


def test_try_approval_returns_none_for_chitchat(db_session) -> None:
    ctx = GatewayContext.from_channel(
        "u1",
        "telegram",
        {"telegram_owner": False, "telegram_role": "blocked"},
    )
    assert try_gateway_approval_route(ctx, "hello there", db_session) is None


def test_compose_llm_reply_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MagicMock(return_value="ok")

    monkeypatch.setattr(
        "app.services.response_engine.compose_nexa_response",
        mock,
    )
    body = NexaGateway().compose_llm_reply("x", "general_chat", MagicMock())
    assert body == "ok"
    assert mock.called


def test_telegram_impl_has_no_removed_nl_approval_regex() -> None:
    """NL approval branches moved to gateway (grep sanity)."""
    root = Path(__file__).resolve().parents[1]
    src = (root / "app" / "bot" / "telegram_bot.py").read_text(encoding="utf-8")
    assert 'if tlow == "approve despite failed tests"' not in src
    assert "approve_commit_match = re.match" not in src

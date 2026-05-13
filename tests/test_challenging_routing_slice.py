# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Regression slice for “challenging” NL routing (ambiguous product, Vercel scaffold, Vercel CLI)."""

from __future__ import annotations

import pytest

from app.services.deployment.vercel_client import ensure_vercel_cli_on_path, vercel_cli_whoami
from app.services.intent_classifier import (
    ambiguous_product_clarification_reply,
    get_intent,
    is_ambiguous_product_request,
    looks_like_external_investigation,
)


def test_ambiguous_website_request() -> None:
    assert is_ambiguous_product_request("Make my website better")
    assert is_ambiguous_product_request("improve my site!")
    assert not is_ambiguous_product_request("make my website faster by lazy-loading images on /shop")
    assert "URL" in ambiguous_product_clarification_reply()


def test_get_intent_ambiguous_before_external() -> None:
    assert get_intent("Make my website better") == "clarification"


def test_portfolio_vercel_not_external_investigation() -> None:
    msg = "Create a portfolio website and deploy to Vercel"
    assert looks_like_external_investigation(msg) is False


def test_vercel_cli_helpers_smoke() -> None:
    st = ensure_vercel_cli_on_path()
    assert "ok" in st
    who = vercel_cli_whoami()
    assert "ok" in who or "error" in who


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_ambiguous_website_clarification(monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean) -> None:
    from app.services.gateway.context import GatewayContext
    from app.services.gateway.runtime import NexaGateway

    monkeypatch.setattr(NexaGateway, "_maybe_auto_dev_investigation", lambda *a, **k: None)
    ctx = GatewayContext.from_channel("u_amb", "web", {"via_gateway": True})
    out = NexaGateway().handle_message(ctx, "Make my website better", db=nexa_runtime_clean)
    assert out.get("intent") == "clarification"
    assert "URL" in (out.get("text") or "")

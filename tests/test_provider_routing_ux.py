# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.provider_routing_ux import build_provider_routing_ux, format_calm_fallback_message


def test_calm_fallback_message() -> None:
    msg = format_calm_fallback_message(provider="Claude Sonnet")
    assert "AethOS temporarily routed" in msg
    assert "Claude Sonnet" in msg
    assert "fallback provider" not in msg.lower()


def test_provider_routing_ux_fallback() -> None:
    truth = {"routing_summary": {"fallback_used": True, "fallback_provider": "sonnet"}}
    out = build_provider_routing_ux(truth)
    msgs = [e["message"] for e in out["provider_routing_ux"]["explanations"]]
    assert any("AethOS" in m for m in msgs)

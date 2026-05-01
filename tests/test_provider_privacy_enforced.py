"""Phase 9 — privacy firewall is mandatory before provider backends."""

from __future__ import annotations

from unittest.mock import patch

from app.services.providers.gateway import call_provider
from app.services.providers.types import ProviderRequest


def test_prepare_external_payload_invoked_before_local_stub():
    seen: list[bool] = []

    def spy_prepare(payload):
        seen.append(True)
        from app.services.privacy_firewall.gateway import prepare_external_payload as real

        return real(payload)

    with patch("app.services.providers.gateway.prepare_external_payload", spy_prepare):
        req = ProviderRequest(
            user_id="u",
            mission_id="m",
            agent_handle="a",
            provider="local_stub",
            model=None,
            purpose="research",
            payload={"task": "Summarize robotics trends", "agent": "R", "tool": "research"},
        )
        resp = call_provider(req)
    assert seen == [True]
    assert resp.ok


def test_blocked_payload_never_reaches_provider_backend():
    req = ProviderRequest(
        user_id="u",
        mission_id="m",
        agent_handle="a",
        provider="openai",
        model=None,
        purpose="x",
        payload={"task": "sk-0123456789012345678901234567890123456789012", "tool": "research"},
    )
    resp = call_provider(req)
    assert resp.blocked
    assert not resp.ok

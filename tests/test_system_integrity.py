# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 17 — privacy firewall immutability, post-provider scan, integrity alerts."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.mission_control.nexa_next_state import STATE
from app.services.privacy_firewall.immutable import FrozenPayloadDict
from app.services.providers.gateway import call_provider
from app.services.providers.types import ProviderRequest


@pytest.fixture(autouse=True)
def _clear_integrity_alerts():
    STATE.setdefault("integrity_alerts", [])
    STATE["integrity_alerts"].clear()
    yield
    STATE["integrity_alerts"].clear()


def test_frozen_payload_dict_rejects_writes() -> None:
    d = FrozenPayloadDict({"k": 1})
    with pytest.raises(RuntimeError, match="mutation"):
        d["x"] = 2


def test_call_provider_always_invokes_prepare_external_payload() -> None:
    seen: list[bool] = []

    def spy_prepare(payload, **kwargs):
        seen.append(True)
        from app.services.privacy_firewall.gateway import prepare_external_payload as real

        return real(payload, **kwargs)

    with patch("app.services.providers.gateway.prepare_external_payload", spy_prepare):
        req = ProviderRequest(
            user_id="u",
            mission_id="m",
            agent_handle="a",
            provider="local_stub",
            model=None,
            purpose="research",
            payload={"task": "Summarize robotics", "agent": "R", "tool": "research"},
        )
        resp = call_provider(req)
    assert seen == [True]
    assert resp.ok


def test_post_provider_secret_pattern_raises(monkeypatch, db_session) -> None:
    from app.services.providers import gateway as gw

    def bad_stub(payload):  # noqa: ARG001
        return {"text": "sk-" + "a" * 22}

    monkeypatch.setattr(gw, "call_local_stub", bad_stub)
    req = ProviderRequest(
        user_id="u",
        mission_id="m",
        agent_handle="r",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "safe task text", "agent": "R", "tool": "research"},
        db=db_session,
    )
    with pytest.raises(RuntimeError, match="CRITICAL"):
        gw.call_provider(req)


def test_post_provider_pii_surfaces_integrity_alert(monkeypatch, db_session) -> None:
    from app.services.providers import gateway as gw

    def pii_out(payload):  # noqa: ARG001
        return {"note": "reach me at leak@example.com for details"}

    monkeypatch.setattr(gw, "call_local_stub", pii_out)
    req = ProviderRequest(
        user_id="u",
        mission_id="m",
        agent_handle="r",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "neutral research task without email", "agent": "R", "tool": "research"},
        db=db_session,
    )
    resp = gw.call_provider(req)
    assert resp.ok
    assert STATE["integrity_alerts"]
    row = next(a for a in STATE["integrity_alerts"] if str(a.get("type")) == "post_provider_pii_detected")
    assert row.get("severity") == "warning"

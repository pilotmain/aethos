# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.privacy.egress_guard import EgressBlocked
from app.privacy.llm_privacy_gate import apply_llm_privacy_gate
from app.services.llm.base import Message


@pytest.fixture
def _fresh():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_llm_gate_redacts_openai_when_redact_mode(monkeypatch: pytest.MonkeyPatch, _fresh) -> None:
    monkeypatch.setenv("AETHOS_PRIVACY_MODE", "redact")
    monkeypatch.setenv("AETHOS_PII_REDACTION_ENABLED", "false")
    s = get_settings()
    msgs = [Message(role="user", content="Email me at user@example.com")]
    out, meta = apply_llm_privacy_gate(msgs, provider_name="openai", model_id="gpt-4o-mini", settings=s)
    assert meta["routing_decision"] == "route_external_redacted"
    assert meta["redactions_applied"] >= 1
    assert "user@example.com" not in str(out[0].content)


def test_llm_gate_blocks_openai_when_block_guard(monkeypatch: pytest.MonkeyPatch, _fresh) -> None:
    monkeypatch.setenv("AETHOS_PRIVACY_MODE", "block")
    monkeypatch.setenv("AETHOS_EXTERNAL_EGRESS_GUARD_ENABLED", "true")
    s = get_settings()
    msgs = [Message(role="user", content="token sk-abcdefghijklmnopqrstuvwxyz0123456789ABCD")]
    with pytest.raises(EgressBlocked) as ei:
        apply_llm_privacy_gate(msgs, provider_name="openai", model_id="gpt-4o-mini", settings=s)
    assert ei.value.payload.get("error") == "privacy_egress_blocked"


def test_llm_gate_allows_ollama_with_pii(monkeypatch: pytest.MonkeyPatch, _fresh) -> None:
    monkeypatch.setenv("AETHOS_PRIVACY_MODE", "block")
    monkeypatch.setenv("AETHOS_EXTERNAL_EGRESS_GUARD_ENABLED", "true")
    s = get_settings()
    msgs = [Message(role="user", content="token sk-abcdefghijklmnopqrstuvwxyz0123456789ABCD")]
    out, meta = apply_llm_privacy_gate(msgs, provider_name="ollama", model_id="qwen", settings=s)
    assert meta["routing_decision"] == "route_local"
    assert "sk-" in str(out[0].content)

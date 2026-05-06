"""Phase 40 — identity strings stay aligned with Nexa-next execution positioning."""

from __future__ import annotations

import pytest

from app.services.gateway.runtime import NexaGateway
from app.services.system_identity.capabilities import (
    CAPABILITIES,
    NEXA_CAPABILITY_REPLY,
    describe_capabilities,
    narrative_capability_answer,
)
from app.services.multi_agent_routing import reply_multi_agent_capability_clarification


_BANNED = (
    "multi-agent command center",
    "command center",
    "route to specialists",
)


def test_capabilities_source_of_truth() -> None:
    caps = describe_capabilities()
    assert caps == CAPABILITIES
    expected_keys = {
        "dev_execution",
        "memory",
        "scheduler",
        "local_models",
        "multi_agent_dynamic",
        "system_access",
    }
    assert set(caps.keys()) == expected_keys
    assert all(caps[k] is True for k in expected_keys)


def test_gateway_describe_capabilities() -> None:
    assert NexaGateway().describe_capabilities() == CAPABILITIES


def test_narrative_capability_answer_identity_and_execution() -> None:
    text = narrative_capability_answer()
    low = text.lower()
    assert "i'm aethos" in low or "im aethos" in low.replace("'", "")
    assert "execute" in low or "execution" in low
    assert "dynamically" in low
    for banned in _BANNED:
        assert banned not in low


def test_narrative_capability_answer_matches_constant() -> None:
    assert narrative_capability_answer() == NEXA_CAPABILITY_REPLY.strip()


@pytest.mark.parametrize(
    ("snippet",),
    [
        (reply_multi_agent_capability_clarification(),),
        (narrative_capability_answer(),),
    ],
)
def test_identity_strings_no_banned_phrases(snippet: str) -> None:
    low = snippet.lower()
    for banned in _BANNED:
        assert banned not in low


def test_multi_agent_clarification_not_legacy_team_pitch() -> None:
    clar = reply_multi_agent_capability_clarification().lower()
    assert "route to specialists" not in clar
    assert "aethos" in clar
    assert "concrete goal" in clar or "goal" in clar
    assert "dynamically" in clar

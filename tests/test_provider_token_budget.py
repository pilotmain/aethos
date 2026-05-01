"""Phase 38 — provider gateway respects token budget."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.mission_control.nexa_next_state import STATE
from app.services.providers.gateway import call_provider
from app.services.providers.types import ProviderRequest


@pytest.fixture(autouse=True)
def _clear_token_state():
    STATE.setdefault("token_audit_tail", []).clear()
    STATE.setdefault("token_economy_usage", {}).clear()
    STATE.setdefault("token_economy_blocks", {}).clear()
    yield


def test_provider_blocks_when_per_request_budget_exceeded(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    monkeypatch.setenv("NEXA_TOKEN_BUDGET_PER_REQUEST", "20")
    monkeypatch.setenv("NEXA_BLOCK_OVER_TOKEN_BUDGET", "true")
    get_settings.cache_clear()

    huge_task = "WORD " * 500  # >> 20 tokens (chars/4)
    req = ProviderRequest(
        user_id="budget_u1",
        mission_id="m1",
        agent_handle="agent",
        provider="local_stub",
        model=None,
        purpose="test",
        payload={
            "task": huge_task,
            "agent": "A",
            "tool": "research",
        },
        db=db_session,
    )
    resp = call_provider(req)
    assert resp.blocked
    assert resp.error in ("token_budget_per_request", "large_context_disabled")
    assert resp.token_estimate is not None

    get_settings.cache_clear()

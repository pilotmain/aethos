"""Phase 10 — emergency disable for remote providers."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.nexa_next_runtime import NexaExternalCall
from app.services.providers.gateway import call_provider
from app.services.providers.types import ProviderRequest


def test_kill_switch_blocks_openai_without_network(monkeypatch, db_session) -> None:
    db_session.execute(delete(NexaExternalCall))
    db_session.commit()

    class _S:
        nexa_disable_external_calls = True
        nexa_provider_rate_limit_per_minute = 99999

    monkeypatch.setattr("app.services.providers.gateway.get_settings", lambda: _S())

    req = ProviderRequest(
        user_id="u_ks",
        mission_id="m_ks",
        agent_handle="a",
        provider="openai",
        model=None,
        purpose="x",
        payload={"task": "hello world here please do something", "tool": "research"},
        db=db_session,
    )
    resp = call_provider(req)
    assert not resp.ok
    assert resp.blocked
    assert resp.error == "external_calls_disabled"

    n = db_session.scalar(select(func.count()).select_from(NexaExternalCall))
    assert n >= 1

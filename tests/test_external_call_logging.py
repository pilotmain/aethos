"""Phase 10 — persistent audit rows for outbound provider attempts."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.nexa_next_runtime import NexaExternalCall
from app.services.providers.gateway import call_provider
from app.services.providers.types import ProviderRequest


def test_call_provider_writes_audit_row(db_session) -> None:
    db_session.execute(delete(NexaExternalCall))
    db_session.commit()

    req = ProviderRequest(
        user_id="u_audit",
        mission_id="m_audit",
        agent_handle="a1",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "hello world task content here", "agent": "A", "tool": "research"},
        db=db_session,
    )
    resp = call_provider(req)
    assert resp.ok

    n = db_session.scalar(select(func.count()).select_from(NexaExternalCall))
    assert n == 1


def test_blocked_attempt_also_logged(db_session) -> None:
    db_session.execute(delete(NexaExternalCall))
    db_session.commit()

    req = ProviderRequest(
        user_id="u_audit",
        mission_id="m_audit",
        agent_handle="a1",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "sk-12345678901234567890123456789012", "tool": "research"},
        db=db_session,
    )
    resp = call_provider(req)
    assert resp.blocked

    n = db_session.scalar(select(func.count()).select_from(NexaExternalCall))
    assert n >= 1
    row = db_session.scalar(select(NexaExternalCall).order_by(NexaExternalCall.id.desc()).limit(1))
    assert row is not None
    assert row.blocked is True

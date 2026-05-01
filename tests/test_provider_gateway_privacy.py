"""Phase 4 — provider gateway + privacy integration."""

from __future__ import annotations

from app.services.artifacts.store import clear_store_for_tests
from app.services.gateway.runtime import NexaGateway
from app.services.mission_control.nexa_next_state import STATE
from app.services.providers.gateway import call_provider
from app.services.providers.types import ProviderRequest


def _clear_ephemeral(db_session) -> None:
    STATE["privacy_events"].clear()
    STATE["provider_events"].clear()
    STATE["last_updated"] = None
    clear_store_for_tests(db_session)


def test_safe_payload_reaches_provider(db_session) -> None:
    _clear_ephemeral(db_session)
    req = ProviderRequest(
        user_id="u1",
        mission_id="m1",
        agent_handle="researcher",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "Researcher: find robotics breakthroughs", "agent": "Researcher", "tool": "research"},
    )
    resp = call_provider(req)
    assert resp.ok
    assert not resp.blocked
    assert resp.output is not None
    assert isinstance(resp.output, dict)
    assert STATE["provider_events"]


def test_email_redacted_before_provider_payload_used(db_session) -> None:
    _clear_ephemeral(db_session)
    req = ProviderRequest(
        user_id="u1",
        mission_id="m1",
        agent_handle="researcher",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "contact john@example.com for data", "agent": "Researcher", "tool": "research"},
    )
    resp = call_provider(req)
    assert resp.ok
    assert resp.redactions
    out = resp.output
    assert isinstance(out, dict)
    assert STATE["privacy_events"]
    assert any(e.get("type") == "pii_redacted" for e in STATE["privacy_events"])


def test_secret_blocks_provider_and_logs_privacy(db_session) -> None:
    _clear_ephemeral(db_session)
    req = ProviderRequest(
        user_id="u1",
        mission_id="m1",
        agent_handle="researcher",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={
            "task": "use sk-123456789012345678901234 please",
            "agent": "Researcher",
            "tool": "research",
        },
    )
    resp = call_provider(req)
    assert resp.blocked
    assert not resp.ok
    assert any(e.get("type") == "secret_blocked" for e in STATE["privacy_events"])
    assert any(e.get("status") == "blocked" for e in STATE["provider_events"])


def test_gateway_mission_with_email_redacts_and_completes(nexa_runtime_clean) -> None:
    text = """Mission: "Privacy Robotics Research"

Researcher: find robotics breakthroughs for john@example.com.
Analyst: write forecast mentioning Researcher.
QA: review risks mentioning Analyst."""
    out = NexaGateway().handle_message(text, "dev_user")
    assert out["status"] == "completed"
    assert STATE["privacy_events"]
    assert STATE["provider_events"]

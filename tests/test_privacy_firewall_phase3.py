"""Phase 3 — privacy gate before tools; Mission Control privacy_events."""

from __future__ import annotations

import pytest

from app.services.artifacts.store import clear_store_for_tests
from app.services.gateway.runtime import NexaGateway
from app.services.mission_control.nexa_next_state import STATE
from app.services.privacy_firewall.audit import LOG as AUDIT_LOG
from app.services.privacy_firewall.gateway import PrivacyBlockedError, prepare_external_payload


def test_prepare_external_safe_payload() -> None:
    payload = prepare_external_payload({"task": "Researcher: find robotics trends", "agent": "Researcher"})
    assert payload["task"] == "Researcher: find robotics trends"


def test_prepare_external_redacts_email() -> None:
    STATE["privacy_events"].clear()
    AUDIT_LOG.clear()
    out = prepare_external_payload({"task": "analyze data from test@email.com", "agent": "Researcher"})
    assert "redacted" in out
    assert "[REDACTED_EMAIL]" in out["redacted"]
    assert STATE["privacy_events"]
    assert AUDIT_LOG


def test_prepare_external_blocks_openai_sk() -> None:
    STATE["privacy_events"].clear()
    AUDIT_LOG.clear()
    with pytest.raises(PrivacyBlockedError, match="Blocked"):
        prepare_external_payload({"task": "use key sk-12345678901234567890", "agent": "Researcher"})
    assert any(e.get("type") == "secret_blocked" for e in STATE["privacy_events"])
    assert AUDIT_LOG


def test_gateway_safe_mission_completes(db_session) -> None:
    STATE["privacy_events"].clear()
    STATE["provider_events"].clear()
    STATE["last_updated"] = None
    clear_store_for_tests(db_session)
    AUDIT_LOG.clear()

    text = """Researcher: find robotics trends here today"""
    out = NexaGateway().handle_message(text, "u_priv")
    assert out["status"] == "completed"


def test_gateway_blocks_secret_in_task(db_session) -> None:
    STATE["privacy_events"].clear()
    STATE["provider_events"].clear()
    clear_store_for_tests(db_session)
    AUDIT_LOG.clear()

    text = """Researcher: use key sk-12345678901234567890 here please"""
    out = NexaGateway().handle_message(text, "u_priv")
    assert out["status"] == "completed"
    agent_row = out["result"][0]
    assert agent_row["output"]["type"] == "blocked"

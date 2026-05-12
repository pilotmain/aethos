# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Week 5 — auto-queue guard (allowlists + success cap)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.sub_agent_autoqueue_guard import (
    reset_autoqueue_counts_for_tests,
    should_run_autoqueue_payload,
)
from app.services.sub_agent_registry import SubAgent


@pytest.fixture(autouse=True)
def _reset_counts() -> None:
    reset_autoqueue_counts_for_tests()
    yield
    reset_autoqueue_counts_for_tests()


def _agent(aid: str = "agent123", domain: str = "git") -> SubAgent:
    return SubAgent(
        id=aid,
        name="t",
        domain=domain,
        capabilities=[],
        parent_chat_id="chat123",
    )


def test_autoqueue_off_skips_domain_checks() -> None:
    """When global autoqueue is false, guard should not block (executor uses queue path)."""
    with patch("app.services.sub_agent_autoqueue_guard.get_settings") as mock_settings:
        mock_settings.return_value.nexa_agent_orchestration_autoqueue = False

        ok, msg, prefer_q = should_run_autoqueue_payload("chat123", "railway", _agent(domain="railway"))
        assert ok is True
        assert msg is None
        assert prefer_q is False


def test_autoqueue_chat_allowlist() -> None:
    with patch("app.services.sub_agent_autoqueue_guard.get_settings") as mock_settings:
        mock_settings.return_value.nexa_agent_orchestration_autoqueue = True
        mock_settings.return_value.nexa_agent_autoqueue_allowlist_chats = "trusted_chat1,trusted_chat2"
        mock_settings.return_value.nexa_agent_autoqueue_allowlist_domains = "git"
        mock_settings.return_value.nexa_agent_autoqueue_require_approval_after = 0

        ok, _, _ = should_run_autoqueue_payload("trusted_chat1", "git", _agent())
        assert ok is True

        ok, err, prefer = should_run_autoqueue_payload("untrusted", "git", _agent())
        assert ok is False
        assert prefer is True
        assert err and "chat" in err.lower()


def test_autoqueue_domain_allowlist() -> None:
    with patch("app.services.sub_agent_autoqueue_guard.get_settings") as mock_settings:
        mock_settings.return_value.nexa_agent_orchestration_autoqueue = True
        mock_settings.return_value.nexa_agent_autoqueue_allowlist_chats = ""
        mock_settings.return_value.nexa_agent_autoqueue_allowlist_domains = "git,vercel"
        mock_settings.return_value.nexa_agent_autoqueue_require_approval_after = 0

        ok, _, _ = should_run_autoqueue_payload("chat123", "git", _agent(domain="git"))
        assert ok is True

        ok, err, prefer = should_run_autoqueue_payload("chat123", "railway", _agent(domain="railway"))
        assert ok is False
        assert prefer is True
        assert "railway" in (err or "").lower() or "domain" in (err or "").lower()


def test_autoqueue_success_threshold_forces_queue() -> None:
    with patch("app.services.sub_agent_autoqueue_guard.get_settings") as mock_settings:
        mock_settings.return_value.nexa_agent_orchestration_autoqueue = True
        mock_settings.return_value.nexa_agent_autoqueue_allowlist_chats = ""
        mock_settings.return_value.nexa_agent_autoqueue_allowlist_domains = "git"
        mock_settings.return_value.nexa_agent_autoqueue_require_approval_after = 1

        # Simulate one successful in-process run already recorded for this agent id
        from app.services.sub_agent_autoqueue_guard import record_autoqueue_success

        record_autoqueue_success("agent123")

        ok, err, prefer = should_run_autoqueue_payload("chat123", "git", _agent(aid="agent123"))
        assert ok is False
        assert prefer is True
        assert err and "cap" in err.lower() or "threshold" in err.lower() or "queue" in err.lower()

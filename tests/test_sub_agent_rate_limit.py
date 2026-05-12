# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Week 5 — sub-agent rate limiting (in-memory, single worker)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.sub_agent_rate_limit import AgentRateLimiter, reset_rate_limiter_for_tests


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_rate_limiter_for_tests()
    yield
    reset_rate_limiter_for_tests()


def test_rate_limit_per_agent() -> None:
    limiter = AgentRateLimiter()
    with patch("app.services.sub_agent_rate_limit.get_settings") as mock_settings:
        mock_settings.return_value.nexa_agent_rate_limit_per_agent = 2
        mock_settings.return_value.nexa_agent_rate_limit_per_chat = 100
        mock_settings.return_value.nexa_agent_rate_limit_per_domain = 100
        mock_settings.return_value.nexa_agent_rate_limit_window_seconds = 60

        agent_id = "test_agent"
        domain = "git"
        chat_id = "chat123"

        ok, _ = limiter.check(agent_id, domain, chat_id)
        assert ok is True
        limiter.record(agent_id, domain, chat_id)

        ok, _ = limiter.check(agent_id, domain, chat_id)
        assert ok is True
        limiter.record(agent_id, domain, chat_id)

        ok, err = limiter.check(agent_id, domain, chat_id)
        assert ok is False
        assert err and "agent" in err.lower()


def test_rate_limit_per_chat() -> None:
    limiter = AgentRateLimiter()
    with patch("app.services.sub_agent_rate_limit.get_settings") as mock_settings:
        mock_settings.return_value.nexa_agent_rate_limit_per_agent = 100
        mock_settings.return_value.nexa_agent_rate_limit_per_chat = 1
        mock_settings.return_value.nexa_agent_rate_limit_per_domain = 100
        mock_settings.return_value.nexa_agent_rate_limit_window_seconds = 60

        ok, _ = limiter.check("agent1", "git", "chat123")
        assert ok is True
        limiter.record("agent1", "git", "chat123")

        ok, err = limiter.check("agent2", "git", "chat123")
        assert ok is False
        assert err and "chat" in err.lower()

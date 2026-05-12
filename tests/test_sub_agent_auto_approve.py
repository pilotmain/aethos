# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Week 5.5 — auto-approve guard."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.sub_agent_auto_approve import should_auto_approve
from app.services.sub_agent_registry import SubAgent


def test_auto_approve_disabled() -> None:
    with patch("app.services.sub_agent_auto_approve.get_settings") as mock_settings:
        mock_settings.return_value.nexa_auto_approve_enabled = False

        ok, reason = should_auto_approve("chat123", "git")
        assert ok is False
        assert reason == "auto_approve_disabled"


def test_auto_approve_chat_allowlist() -> None:
    with patch("app.services.sub_agent_auto_approve.get_settings") as mock_settings:
        mock_settings.return_value.nexa_auto_approve_enabled = True
        mock_settings.return_value.nexa_auto_approve_chats = "trusted_chat"
        mock_settings.return_value.nexa_auto_approve_domains = "git"
        mock_settings.return_value.nexa_auto_approve_log_only = False

        ok, _ = should_auto_approve("trusted_chat", "git")
        assert ok is True

        ok, reason = should_auto_approve("untrusted", "git")
        assert ok is False
        assert reason == "chat_not_allowlisted"


def test_auto_approve_domain_allowlist() -> None:
    with patch("app.services.sub_agent_auto_approve.get_settings") as mock_settings:
        mock_settings.return_value.nexa_auto_approve_enabled = True
        mock_settings.return_value.nexa_auto_approve_chats = ""
        mock_settings.return_value.nexa_auto_approve_domains = "git,vercel"
        mock_settings.return_value.nexa_auto_approve_log_only = False

        ok, _ = should_auto_approve("any_chat", "git")
        assert ok is True

        ok, reason = should_auto_approve("any_chat", "railway")
        assert ok is False
        assert reason == "domain_not_allowlisted"


def test_auto_approve_log_only() -> None:
    with patch("app.services.sub_agent_auto_approve.get_settings") as mock_settings:
        mock_settings.return_value.nexa_auto_approve_enabled = True
        mock_settings.return_value.nexa_auto_approve_chats = "trusted_chat"
        mock_settings.return_value.nexa_auto_approve_domains = "git"
        mock_settings.return_value.nexa_auto_approve_log_only = True

        ok, reason = should_auto_approve("trusted_chat", "git")
        assert ok is False
        assert reason == "log_only_mode"


def test_auto_approve_trusted_agent_bypasses_lists() -> None:
    agent = SubAgent(
        id="a1",
        name="g",
        domain="git",
        capabilities=[],
        parent_chat_id="x",
        trusted=True,
    )
    with patch("app.services.sub_agent_auto_approve.get_settings") as mock_settings:
        mock_settings.return_value.nexa_auto_approve_enabled = True
        mock_settings.return_value.nexa_auto_approve_chats = "other_only"
        mock_settings.return_value.nexa_auto_approve_domains = "vercel"
        mock_settings.return_value.nexa_auto_approve_log_only = False

        ok, reason = should_auto_approve("not_in_chat_list", "railway", agent=agent)
        assert ok is True
        assert reason == "trusted_agent"

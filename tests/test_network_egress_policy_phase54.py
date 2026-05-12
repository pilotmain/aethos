# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.core.config import get_settings
from app.services.network_policy.policy import assert_provider_egress_allowed, is_egress_allowed


def test_allowlist_permits_anthropic_host(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_NETWORK_EGRESS_MODE", "allowlist")
    monkeypatch.setenv("NEXA_NETWORK_ALLOWED_HOSTS", "api.anthropic.com")
    get_settings.cache_clear()
    try:
        assert is_egress_allowed("https://api.anthropic.com/v1/messages", "test", "u1") is True
        assert assert_provider_egress_allowed("anthropic", "u1") is None
    finally:
        get_settings.cache_clear()


def test_deny_blocks_remote(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_NETWORK_EGRESS_MODE", "deny")
    get_settings.cache_clear()
    try:
        assert is_egress_allowed("https://api.anthropic.com/", "test", None) is False
        assert is_egress_allowed("http://127.0.0.1:11434/", "test", None) is True
    finally:
        get_settings.cache_clear()

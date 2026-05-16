# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.gateway.operator_intent_router import execute_provider_nl_intent
from app.gateway.provider_intents import parse_provider_operation_intent


def test_privacy_block_on_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    try:
        monkeypatch.setattr(
            "app.gateway.operator_intent_router._privacy_allows_provider_nl",
            lambda _t: (False, "blocked by policy"),
        )
        parsed = parse_provider_operation_intent("scan providers")
        assert parsed is not None
        out = execute_provider_nl_intent(parsed)
        assert out.get("intent") == "privacy_blocked"
        assert "block" in (out.get("text") or "").lower()
    finally:
        get_settings.cache_clear()

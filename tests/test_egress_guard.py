# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.privacy.egress_guard import evaluate_egress


@pytest.fixture
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_evaluate_egress_blocks_when_guard_on(monkeypatch: pytest.MonkeyPatch, tmp_path, _fresh_settings) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AETHOS_PRIVACY_MODE", "block")
    monkeypatch.setenv("AETHOS_EXTERNAL_EGRESS_GUARD_ENABLED", "true")
    s = get_settings()
    ok, reason = evaluate_egress(s, "http", pii_categories=["email"])
    assert not ok
    assert reason == "blocked_pii_present"

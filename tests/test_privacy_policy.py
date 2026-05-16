# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json

import pytest

from app.core.config import get_settings
from app.privacy.egress_guard import evaluate_egress
from app.privacy.privacy_modes import PrivacyMode
from app.privacy.privacy_policy import current_privacy_mode


@pytest.fixture
def _fresh_settings(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_invalid_privacy_mode_coerces_to_observe(monkeypatch: pytest.MonkeyPatch, _fresh_settings) -> None:
    monkeypatch.setenv("AETHOS_PRIVACY_MODE", "nope")
    s = get_settings()
    assert s.aethos_privacy_mode == "observe"


def test_current_privacy_mode_enum(monkeypatch: pytest.MonkeyPatch, _fresh_settings) -> None:
    monkeypatch.setenv("AETHOS_PRIVACY_MODE", "redact")
    s = get_settings()
    assert current_privacy_mode(s) == PrivacyMode.REDACT


def test_evaluate_egress_off_skips_audit(monkeypatch: pytest.MonkeyPatch, tmp_path, _fresh_settings) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AETHOS_PRIVACY_MODE", "off")
    monkeypatch.setenv("AETHOS_PRIVACY_AUDIT_ENABLED", "true")
    s = get_settings()
    ok, reason = evaluate_egress(s, "llm", pii_categories=["email"])
    assert ok and reason == "off"
    log = tmp_path / ".aethos" / "logs" / "privacy.log"
    assert not log.is_file()

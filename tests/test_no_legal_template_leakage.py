# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Post-LLM sanitizer removes regulated-template leakage in developer mode."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.response_sanitizer import sanitize_developer_mode_stale_copy


@pytest.fixture
def dev_mode(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "developer")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_sanitizer_strips_legal_assistant_line(dev_mode) -> None:
    raw = (
        "Role:\n"
        "Legal research and contract review assistant\n\n"
        "Here is the answer: ok."
    )
    out = sanitize_developer_mode_stale_copy(raw)
    assert "Legal research and contract review" not in out
    assert "ok" in out.lower()


def test_sanitizer_noop_in_regulated_workspace(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    get_settings.cache_clear()
    try:
        raw = "Legal research and contract review assistant\n\nhello"
        assert sanitize_developer_mode_stale_copy(raw) == raw
    finally:
        get_settings.cache_clear()

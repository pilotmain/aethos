"""Offline / strict privacy runtime hints and gateway behavior (Phase 13)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.mission_control.nexa_next_state import _runtime_hints
from app.services.providers.gateway import call_provider
from app.services.providers.types import ProviderRequest


def test_runtime_hints_offline_without_remote_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        openai_api_key=None,
        anthropic_api_key="",
        nexa_disable_external_calls=False,
        nexa_strict_privacy_mode=False,
    )
    monkeypatch.setattr(
        "app.services.mission_control.nexa_next_state.get_settings",
        lambda: fake,
    )
    h = _runtime_hints()
    assert h["offline_mode"] is True
    assert h["remote_providers_available"] is False


def test_runtime_hints_not_offline_when_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        openai_api_key="sk-test",
        anthropic_api_key=None,
        nexa_disable_external_calls=False,
        nexa_strict_privacy_mode=False,
    )
    monkeypatch.setattr(
        "app.services.mission_control.nexa_next_state.get_settings",
        lambda: fake,
    )
    assert _runtime_hints()["offline_mode"] is False


def test_runtime_hints_strict_privacy_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        openai_api_key=None,
        anthropic_api_key=None,
        nexa_disable_external_calls=False,
        nexa_strict_privacy_mode=True,
    )
    monkeypatch.setattr(
        "app.services.mission_control.nexa_next_state.get_settings",
        lambda: fake,
    )
    assert _runtime_hints()["strict_privacy_mode"] is True


def test_strict_privacy_blocks_openai(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    fake = SimpleNamespace(
        nexa_strict_privacy_mode=True,
        nexa_disable_external_calls=False,
        nexa_provider_rate_limit_per_minute=999_999,
        openai_api_key="sk-test",
        anthropic_api_key=None,
    )
    monkeypatch.setattr("app.services.providers.gateway.get_settings", lambda: fake)

    req = ProviderRequest(
        user_id="web_test_strict",
        mission_id="m1",
        agent_handle="researcher",
        provider="openai",
        model="gpt-4o-mini",
        purpose="test",
        payload={
            "tool": "research",
            "task": "Say hello only.",
            "agent": "researcher",
        },
        db=db_session,
    )
    out = call_provider(req)
    assert out.ok is False
    assert out.blocked is True
    assert (out.error or "") == "strict_privacy_mode"

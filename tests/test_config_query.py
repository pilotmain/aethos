"""Phase 77 — configuration Q&A intent and handler."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.config_query import handle_config_query
from app.services.intent_classifier import get_intent, is_config_query


def test_is_config_query_detection() -> None:
    assert is_config_query("what model are you using") is True
    assert is_config_query("Which LLM is running on this bot?") is True
    assert is_config_query("show me my workspace") is True
    assert is_config_query("what settings do I have") is True
    assert is_config_query("deploy my app to Railway") is False


def test_get_intent_config_query_short_circuits() -> None:
    assert get_intent("what model are we using?") == "config_query"


def test_handle_model_query(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        nexa_llm_provider="anthropic",
        nexa_llm_model="claude-3-sonnet-20240229",
        anthropic_api_key="x",
        anthropic_model="claude-haiku-4-5",
        openai_api_key=None,
        openai_model="gpt-4o-mini",
        deepseek_api_key=None,
        deepseek_model="deepseek-chat",
    )

    monkeypatch.setattr("app.services.config_query.get_settings", lambda: fake)
    response = handle_config_query("what model are you using")
    assert "claude-3-sonnet" in response


def test_handle_workspace_query(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        host_executor_work_root="/tmp/work",
        nexa_workspace_root="/tmp/projects",
    )
    monkeypatch.setattr("app.services.config_query.get_settings", lambda: fake)
    body = handle_config_query("where is my workspace")
    assert "/tmp/work" in body or "workspace" in body.lower()


def test_api_key_status_never_echoes_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        openai_api_key="sk-secret",
        anthropic_api_key=None,
        deepseek_api_key=None,
        openrouter_api_key=None,
        nexa_llm_api_key="",
    )
    monkeypatch.setattr("app.services.config_query.get_settings", lambda: fake)
    body = handle_config_query("what API keys are configured")
    assert "sk-" not in body
    assert "configured" in body.lower() or "not set" in body.lower()

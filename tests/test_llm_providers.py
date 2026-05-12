"""Phase 11 — multi-provider LLM registry and OpenAI-compatible backends."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.llm.base import Message
from app.services.llm.bootstrap import register_llm_providers_from_settings
from app.services.llm.providers.openai_backend import OpenAIBackend
from app.services.llm.registry import get_llm_registry, reset_llm_registry_for_tests


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_llm_registry_for_tests()
    yield
    reset_llm_registry_for_tests()


def test_openai_backend_complete_invokes_chat_api():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "ok-from-model"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("app.services.llm.providers.openai_backend.build_openai_client", return_value=mock_client):
        p = OpenAIBackend(
            logical_name="openai",
            api_key="k",
            model="gpt-4o-mini",
            used_user_key=False,
        )
        out = p.complete_chat([Message(role="user", content="hi")], temperature=0.2, max_tokens=8)
    assert out == "ok-from-model"
    mock_client.chat.completions.create.assert_called_once()


def test_openai_messages_include_tool_and_system_roles():
    p = OpenAIBackend(logical_name="t", api_key="k", model="m")
    with patch("app.services.llm.providers.openai_backend.build_openai_client") as b:
        b.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="x"))]
        )
        p.complete_chat(
            [
                Message(role="system", content="sys"),
                Message(role="user", content="u"),
            ],
            temperature=0.1,
        )
    call_kw = b.return_value.chat.completions.create.call_args[1]
    rows = call_kw["messages"]
    assert rows[0]["role"] == "system"
    assert rows[1]["role"] == "user"


@patch("app.services.llm.bootstrap.get_settings")
@patch("app.services.llm.bootstrap.get_merged_api_keys")
def test_registry_registers_openai_when_key_present(m_merge, m_settings):
    m_settings.return_value = MagicMock(
        nexa_llm_provider="openai",
        openai_model="gpt-4o-mini",
        openai_api_key="",
        anthropic_api_key="",
        anthropic_model="claude-haiku-4-5-20251001",
        nexa_llm_intelligence_level="balanced",
        nexa_llm_intelligence_apply_to_anthropic=False,
        deepseek_api_key="",
        deepseek_model="deepseek-chat",
        deepseek_base_url=None,
        openrouter_api_key="",
        openrouter_model="openai/gpt-4o-mini",
        openrouter_base_url=None,
        nexa_ollama_base_url=None,
        nexa_ollama_default_model="llama3",
        nexa_ollama_enabled=False,
        nexa_local_first=False,
        nexa_provider_timeout_seconds=15.0,
        nexa_llm_model=None,
        nexa_llm_api_key=None,
        nexa_llm_base_url=None,
    )
    m_merge.return_value = MagicMock(
        openai_api_key="sk-test",
        anthropic_api_key=None,
        has_user_openai=False,
        has_user_anthropic=False,
    )
    reg = register_llm_providers_from_settings()
    p = reg.get_provider("openai")
    assert p is not None
    assert p.get_model_info().provider == "openai"


def test_get_llm_registry_list_providers_empty_after_reset():
    r = get_llm_registry()
    assert r.list_providers() == []

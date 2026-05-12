# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 39 — Ollama local provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.providers.ollama_provider import call_ollama


def test_call_ollama_parses_chat_response() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(
        return_value={"model": "llama3", "message": {"role": "assistant", "content": "hello local"}}
    )
    with patch("httpx.Client") as client_cls:
        inst = MagicMock()
        inst.__enter__ = MagicMock(return_value=inst)
        inst.__exit__ = MagicMock(return_value=False)
        inst.post = MagicMock(return_value=mock_resp)
        client_cls.return_value = inst
        out = call_ollama(
            {"task": "ping", "tool": "research"},
            base_url="http://127.0.0.1:11434",
            model="llama3",
            timeout_seconds=5.0,
        )
    assert out.get("provider") == "ollama"
    assert out.get("text") == "hello local"


def test_call_ollama_empty_task() -> None:
    out = call_ollama({}, base_url="http://127.0.0.1:11434", model="m", timeout_seconds=1.0)
    assert out.get("error") == "empty_task"

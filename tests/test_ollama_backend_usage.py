# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Ollama backend records LLM usage for web chat model badges."""

from __future__ import annotations

import pytest

from app.services.llm.base import Message
from app.services.llm.providers import ollama_backend as ob


def test_ollama_complete_chat_records_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def cap(db=None, **kwargs: object) -> None:  # noqa: ANN001
        captured["db"] = db
        captured.update(kwargs)

    class Resp:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "message": {"role": "assistant", "content": "hello"},
                "prompt_eval_count": 5,
                "eval_count": 3,
            }

    class Client:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def post(self, url: str, json: dict | None = None) -> Resp:
            return Resp()

    monkeypatch.setattr(ob, "record_llm_usage", cap)
    monkeypatch.setattr(ob.httpx, "Client", Client)

    b = ob.OllamaBackend(base_url="http://127.0.0.1:11434", model="phi3:mini")
    out = b.complete_chat([Message(role="user", content="hi")])
    assert out == "hello"
    assert captured.get("provider") == "ollama"
    assert captured.get("model") == "phi3:mini"
    assert captured.get("input_tokens") == 5
    assert captured.get("output_tokens") == 3

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Catalog of local / OpenAI-compatible inference endpoints (documentation + discovery helpers)."""

from __future__ import annotations

from typing import Any

_LOCAL_RUNTIMES: list[dict[str, Any]] = [
    {
        "id": "ollama",
        "label": "Ollama",
        "default_base": "http://127.0.0.1:11434",
        "protocol": "openai_compatible",
    },
    {
        "id": "lm_studio",
        "label": "LM Studio",
        "default_base": "http://127.0.0.1:1234",
        "protocol": "openai_compatible",
    },
    {
        "id": "llama_cpp_server",
        "label": "llama.cpp server",
        "default_base": "http://127.0.0.1:8080",
        "protocol": "openai_compatible",
    },
    {
        "id": "vllm",
        "label": "vLLM",
        "default_base": "http://127.0.0.1:8000",
        "protocol": "openai_compatible",
    },
    {
        "id": "generic_openai_compat",
        "label": "Generic OpenAI-compatible HTTP",
        "default_base": "http://127.0.0.1:3000",
        "protocol": "openai_compatible",
    },
]


def list_local_runtimes() -> list[dict[str, Any]]:
    return list(_LOCAL_RUNTIMES)


__all__ = ["list_local_runtimes"]

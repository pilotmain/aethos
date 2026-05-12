# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""OpenAI-compatible HTTP chat helper (Phase 52 scaffolding).

Wire concrete transports through ``safe_llm_gateway`` in production; this module holds URL/key shapes.
"""

from __future__ import annotations

from typing import Any


def describe_openai_compatible_env(provider_id: str, *, base_url_env: str | None, api_key_env: str) -> dict[str, Any]:
    """Human-readable env hints for docs and Mission Control copy."""
    return {
        "provider_id": provider_id,
        "base_url_env": base_url_env,
        "api_key_env": api_key_env,
        "pattern": "Set BASE_URL + API key for OpenAI-compatible endpoints (local Ollama, vLLM, gateways).",
    }


__all__ = ["describe_openai_compatible_env"]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 52C — OpenAI-compatible env description helper."""

from __future__ import annotations

from app.services.providers.openai_compatible_provider import describe_openai_compatible_env


def test_describe_openai_compatible_env_includes_ids() -> None:
    d = describe_openai_compatible_env("deepseek", base_url_env="NEXA_PROVIDER_DEEPSEEK_BASE_URL", api_key_env="DEEPSEEK_API_KEY")
    assert d["provider_id"] == "deepseek"
    assert d["api_key_env"] == "DEEPSEEK_API_KEY"
    assert "OpenAI-compatible" in d.get("pattern", "")

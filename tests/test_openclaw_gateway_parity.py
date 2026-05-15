# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Gateway / LLM-first routing parity hooks — see docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md §1."""

from __future__ import annotations

from app.core.config import Settings


def test_llm_first_gateway_setting_exists() -> None:
    assert "nexa_llm_first_gateway" in Settings.model_fields

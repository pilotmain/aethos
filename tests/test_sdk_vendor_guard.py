# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 16 — SDK builders allow pytest contexts (stack inspection)."""

from __future__ import annotations

from app.services.providers.sdk import build_openai_client


def test_build_openai_client_allowed_under_pytest() -> None:
    """Orchestration guard allows ``tests.*`` call stacks."""
    build_openai_client(api_key="sk-test-invalid-for-real-call")

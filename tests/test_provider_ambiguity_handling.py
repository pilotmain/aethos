# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.gateway.operator_intent_router import execute_provider_nl_intent


def test_ambiguous_project_returns_clarification() -> None:
    parsed = {
        "intent": "provider_restart",
        "raw_text": "restart demo",
        "environment": "production",
        "provider": "vercel",
        "project_phrase": "demo",
        "project_id": None,
        "candidates": [
            {"project_id": "demo-a", "repo_path": "/a"},
            {"project_id": "demo-b", "repo_path": "/b"},
        ],
    }
    out = execute_provider_nl_intent(parsed)
    text = out.get("text") or ""
    assert "demo-a" in text or "candidates" in text.lower()
    assert out.get("success") is False

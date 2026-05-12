# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 19 — detection explainability helpers."""

from __future__ import annotations

from app.services.privacy_firewall.explainability import explain_detection


def test_explain_detection_includes_reason_and_patterns() -> None:
    out = explain_detection(
        {
            "secrets": ["jwt"],
            "pii": ["email"],
            "confidence": "medium",
        }
    )
    assert out["confidence"] == "medium"
    assert "jwt" in out["matched_pattern"] and "email" in out["matched_pattern"]
    assert out["pattern"] == out["matched_pattern"]
    assert "Secret-shaped" in out["reason"] or "secret" in out["reason"].lower()
    assert "email" in out["reason"].lower()


def test_explain_detection_empty_findings() -> None:
    out = explain_detection({"secrets": [], "pii": [], "confidence": "low"})
    assert out["confidence"] == "low"
    assert out["matched_pattern"] == "none"

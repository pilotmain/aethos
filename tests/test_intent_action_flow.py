# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 49 — intent routing favors action paths (stuck_dev vs stuck)."""

from __future__ import annotations

from app.services.intent_classifier import classify_intent_fallback, get_intent, looks_like_stuck_dev
from app.services.legacy_behavior_utils import Context, map_intent_to_behavior


def test_looks_like_stuck_dev_positive() -> None:
    assert looks_like_stuck_dev("pytest fails with ImportError — I'm stuck")
    assert looks_like_stuck_dev("docker build fails and I can't figure out why")


def test_looks_like_stuck_dev_negative() -> None:
    assert not looks_like_stuck_dev("I'm stuck on my taxes")
    assert not looks_like_stuck_dev("hello")


def test_fallback_prefers_stuck_dev_over_generic_stuck() -> None:
    r = classify_intent_fallback("npm install fails with ENOTFOUND — help me fix")
    assert r["intent"] == "stuck_dev"


def test_map_intent_stuck_dev_routes_to_unstick_behavior() -> None:
    ctx = Context(
        user_id="u",
        tasks=[],
        last_plan=[],
        memory={},
    )
    assert map_intent_to_behavior("stuck_dev", ctx) == "unstick"


def test_get_intent_upgrade_stuck_to_stuck_dev(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.intent_classifier.classify_intent_llm",
        lambda msg, conversation_snapshot=None, **_: {
            "intent": "stuck",
            "confidence": 0.95,
            "reason": "mock",
        },
    )
    assert get_intent("kubernetes ingress returns 502 every time — ERROR") == "stuck_dev"

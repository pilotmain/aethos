# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.operational_intelligence_engine import (
    build_intelligence_signals,
    build_operational_intelligence_engine,
    build_proactive_suggestions,
)


def test_engine_shape() -> None:
    eng = build_operational_intelligence_engine()
    assert "signals" in eng
    assert "suggestions" in eng
    assert "runtime_insights" in eng
    assert "enterprise_operational_state" in eng
    assert "summaries" in eng


def test_signals_and_suggestions() -> None:
    signals = build_intelligence_signals({})
    suggestions = build_proactive_suggestions(signals)
    assert isinstance(signals, list)
    assert isinstance(suggestions, list)

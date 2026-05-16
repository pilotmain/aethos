# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.operational_intelligence_engine import build_intelligence_signals


def test_provider_signal_type_exists() -> None:
    signals = build_intelligence_signals({"reliability": {"provider_failures": 2}})
    kinds = {s.get("kind") for s in signals}
    assert "provider_instability_trend" in kinds

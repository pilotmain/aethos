# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.operational_intelligence_engine import build_operational_intelligence_engine


def test_engine_with_provider_failures() -> None:
    eng = build_operational_intelligence_engine({"reliability": {"provider_failures": 3}})
    kinds = {s.get("kind") for s in eng.get("signals") or []}
    assert "provider_instability_trend" in kinds or eng.get("insights")

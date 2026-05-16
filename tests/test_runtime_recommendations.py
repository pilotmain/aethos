# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.runtime_recommendations import build_runtime_recommendations


def test_recommendations_bounded() -> None:
    out = build_runtime_recommendations()
    assert "recommendations" in out
    assert len(out["recommendations"]) <= 12
    for r in out["recommendations"]:
        assert r.get("advisory") is True
        assert "confidence" in r

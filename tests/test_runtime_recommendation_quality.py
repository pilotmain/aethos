# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.runtime_recommendations import build_runtime_recommendations


def test_recommendation_rich_fields() -> None:
    out = build_runtime_recommendations({"reliability": {"provider_failures": 2}})
    recs = out.get("recommendations") or []
    if recs:
        r = recs[0]
        assert "reason" in r
        assert "suggested_next_step" in r
        assert r.get("requires_approval") is True

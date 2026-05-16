# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.intelligent_routing import build_intelligent_routing


def test_intelligent_routing_advisory() -> None:
    out = build_intelligent_routing({"routing_summary": {"fallback_used": True}})
    assert out["advisory_first"] is True
    assert out["routing_governance"]["no_hidden_routing"] is True

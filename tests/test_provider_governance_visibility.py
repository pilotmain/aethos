# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.provider_governance_visibility import (
    build_provider_governance,
    build_provider_history,
    build_provider_trust,
)


def test_provider_governance_and_trust() -> None:
    gov = build_provider_governance({})
    assert "recent_actions" in gov
    trust = build_provider_trust({})
    assert 0.0 <= float(trust.get("score") or 0) <= 1.0
    hist = build_provider_history(limit=8)
    assert "actions" in hist

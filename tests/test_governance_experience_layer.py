# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.governance_experience_layer import build_governance_experience_layer


def test_governance_experience_layer_bounded() -> None:
    out = build_governance_experience_layer({"operational_trust_score": 0.9, "runtime_escalations": {"escalation_count": 0}})
    assert out["governance_experience_layer"]["bounded"] is True
    assert isinstance(out["operational_governance_story"], str)

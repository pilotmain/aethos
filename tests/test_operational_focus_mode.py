# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.operator_trust_experience import build_runtime_focus_mode


def test_operational_focus_mode_escalation_view() -> None:
    out = build_runtime_focus_mode({"runtime_escalations": {"escalation_count": 2}})
    assert out["escalation_only_view"] is True

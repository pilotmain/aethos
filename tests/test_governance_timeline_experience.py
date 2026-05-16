# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.governance_timeline_experience import build_governance_timeline_experience


def test_timeline_experience() -> None:
    out = build_governance_timeline_experience(
        {"unified_operational_timeline": {"timeline": [{"kind": "deployment", "what": "Ship"}]}}
    )
    assert out["timeline_experience"]["human_readable"] is True
    assert isinstance(out["governance_story_windows"], list)

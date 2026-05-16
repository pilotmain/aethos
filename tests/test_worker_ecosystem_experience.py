# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.worker_ecosystem_experience import build_worker_ecosystem_experience


def test_worker_ecosystem_experience() -> None:
    out = build_worker_ecosystem_experience({"runtime_workers": {"active_count": 2}})
    assert out["worker_ecosystem_experience"]["enterprise_readable"] is True
    assert out["lifecycle_storytelling"]["orchestrator_led"] is True
    assert "worker_collaboration_story" in out

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_office_launch_quality import enrich_office_launch_payload


def test_office_launch_quality() -> None:
    out = enrich_office_launch_payload({"hydration_progress": {"partial": True, "tiers_complete": ["critical"]}})
    assert out["office_launch_quality"]["launch_grade"] is True
    assert "warming" in out["runtime_readiness_summary"].lower()

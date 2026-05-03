from __future__ import annotations

from app.services.mission_control.safety_readiness import build_safety_readiness_snapshot


def test_safety_readiness_snapshot_keys() -> None:
    snap = build_safety_readiness_snapshot(user_id="test-user")
    assert "sandbox_mode" in snap
    assert "network_egress_mode" in snap
    assert "skill_package_count" in snap

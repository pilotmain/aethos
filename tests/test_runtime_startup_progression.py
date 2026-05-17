# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_startup_experience import build_runtime_startup_experience


def test_startup_progressive_unlock() -> None:
    out = build_runtime_startup_experience({"hydration_progress": {"partial": True}})["runtime_startup_experience"]
    assert "office" in out.get("progressive_surface_unlock", [])
    assert out.get("alive_progressive_operational") is True

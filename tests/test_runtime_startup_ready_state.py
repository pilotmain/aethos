# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_startup_experience import (
    build_runtime_hydration_stages,
    build_runtime_readiness,
    build_runtime_startup_experience,
)


def test_runtime_startup_ready_state() -> None:
    exp = build_runtime_startup_experience({"hydration_progress": {"partial": True, "tiers_complete": ["critical"]}})
    assert exp["runtime_startup_experience"]["no_white_screen"] is True
    stages = build_runtime_hydration_stages({})
    assert stages["runtime_hydration_stages"]["stages"]
    ready = build_runtime_readiness({})
    assert "ready" in ready["runtime_readiness"]

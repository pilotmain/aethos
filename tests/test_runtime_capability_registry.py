# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_api_capabilities import (
    MC_COMPATIBILITY_VERSION,
    build_runtime_capabilities,
    route_available,
)


def test_capabilities_registry() -> None:
    caps = build_runtime_capabilities()
    assert caps["mc_compatibility_version"] == "phase4_step8"
    assert caps["feature_flags"]["runtime_resilience"] is True
    assert route_available("GET", "/api/v1/mission-control/state")

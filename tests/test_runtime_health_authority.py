# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_health_authority import build_canonical_runtime_health


def test_runtime_health_authority_keys() -> None:
    blob = build_canonical_runtime_health()
    ha = blob["runtime_health_authority"]
    for key in (
        "api_reachable",
        "mission_control_reachable",
        "database_healthy",
        "ownership_valid",
        "hydration_active",
        "operational",
        "stale_session",
        "readiness_state",
    ):
        assert key in ha

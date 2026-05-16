# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_api_capabilities import build_runtime_capabilities


def test_runtime_capabilities_includes_setup_and_runtime() -> None:
    caps = build_runtime_capabilities()
    paths = {r["path"] for r in caps["available_routes"]}
    assert "/api/v1/setup/status" in paths
    assert "/api/v1/runtime/routing" in paths
    assert caps["mc_compatibility_version"] == "phase4_step11"

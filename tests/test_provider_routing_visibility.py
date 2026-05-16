# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_routing_visibility import (
    build_provider_health_matrix,
    build_routing_explanations,
    build_routing_history,
)


def test_routing_visibility() -> None:
    assert build_routing_history({})["bounded"] is True
    assert "current" in build_routing_explanations({})
    assert build_provider_health_matrix({})["bounded"] is True

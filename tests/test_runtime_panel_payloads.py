# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_panels import build_runtime_panels


def test_runtime_panels_keys() -> None:
    p = build_runtime_panels("user1")
    assert "runtime_health" in p
    assert "brain_routing" in p
    assert "provider_operations" in p
    assert "runtime_agents" in p

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.runtime_agents import office_topology


def test_office_topology_shape() -> None:
    t = office_topology()
    assert "agents" in t
    assert "ownership_chains" in t
    assert "recent_events" in t

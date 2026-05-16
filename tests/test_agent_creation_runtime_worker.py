# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import find_runtime_agent_by_handle, link_registry_agent_to_runtime


def test_link_registry_creates_runtime_worker() -> None:
    row = link_registry_agent_to_runtime(
        registry_agent_id="reg123",
        name="market_researcher",
        domain="marketing",
    )
    assert row.get("handle") == "@market_researcher_agent"
    assert row.get("registry_agent_id") == "reg123"
    found = find_runtime_agent_by_handle("market_researcher")
    assert found is not None
    assert found.get("role") == "marketing"

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import link_registry_agent_to_runtime
from app.services.agent_runtime_truth import try_route_agent_status_query


def test_status_query_routed_before_dispatch() -> None:
    link_registry_agent_to_runtime(registry_agent_id="r3", name="status_bot", domain="qa")
    out = try_route_agent_status_query(
        "what is the result of @status_bot work?",
        "web:u1:default",
        user_id="u1",
    )
    assert out and out.get("handled")
    assert "don't have visibility" not in (out.get("response") or "").lower()
    assert "no task" in (out.get("response") or "").lower() or "exists" in (out.get("response") or "").lower()

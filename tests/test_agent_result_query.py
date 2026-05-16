# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import link_registry_agent_to_runtime
from app.services.agent_runtime_truth import extract_agent_query_handle, format_agent_status_reply


def test_extract_result_query_handle() -> None:
    h = extract_agent_query_handle("what is the result of @market_researcher_agent work?")
    assert h == "market_researcher_agent" or h == "market_researcher"


def test_idle_agent_no_task_message() -> None:
    link_registry_agent_to_runtime(registry_agent_id="r2", name="idle_bot", domain="general")
    reply = format_agent_status_reply("idle_bot")
    assert "exists" in reply.lower()
    assert "no task" in reply.lower()


def test_no_visibility_phrase_absent() -> None:
    reply = format_agent_status_reply("nonexistent_xyz_agent")
    assert "don't have visibility" not in reply.lower()
    assert "not found" in reply.lower() or "was not found" in reply.lower()

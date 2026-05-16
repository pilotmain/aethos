# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import find_runtime_agent_by_registry_id, link_registry_agent_to_runtime
from app.services.agent_runtime_truth import format_agent_status_reply


def test_subagent_show_uses_runtime() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="show1", name="show_me", domain="ops")
    rt = find_runtime_agent_by_registry_id("show1")
    assert rt is not None
    reply = format_agent_status_reply("show_me", runtime=rt)
    assert "@show_me" in reply or "show_me" in reply

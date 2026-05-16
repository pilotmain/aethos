# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import link_registry_agent_to_runtime
from app.runtime.runtime_agents import set_runtime_agent_status


def test_expired_agent_keeps_history_field() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="h1", name="hist_bot", domain="general")
    aid = str(row["agent_id"])
    set_runtime_agent_status(aid, "expired")
    from app.runtime.agent_work_state import find_runtime_agent_by_handle

    rt = find_runtime_agent_by_handle("hist_bot")
    assert rt is not None
    assert isinstance(rt.get("history"), list)

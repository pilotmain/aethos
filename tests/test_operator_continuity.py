# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import persist_deliverable, set_session_active_worker
from app.services.operator_continuity import resolve_operator_continuity


def test_continue_where_we_left_off() -> None:
    from app.runtime.agent_work_state import link_registry_agent_to_runtime

    row = link_registry_agent_to_runtime(registry_agent_id="oc1", name="ops", domain="ops")
    aid = str(row["agent_id"])
    persist_deliverable(
        worker_id=aid,
        task_id="t1",
        deliverable_type="deployment_report",
        summary="deploy check",
        content="ok",
    )
    set_session_active_worker("web:oc", aid)
    reply, src = resolve_operator_continuity("continue where we left off", chat_key="web:oc")
    assert reply and src == "operator_resume"
    assert "Continuing" in reply

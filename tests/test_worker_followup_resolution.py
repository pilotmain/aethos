# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import link_registry_agent_to_runtime
from app.runtime.worker_operational_memory import persist_deliverable, set_session_active_worker
from app.services.worker_intelligence import resolve_worker_followup


def test_what_did_you_find_uses_session_worker() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="f1", name="researcher", domain="marketing")
    aid = str(row["agent_id"])
    persist_deliverable(
        worker_id=aid,
        task_id="t1",
        deliverable_type="research_summary",
        summary="findings",
        content="Alpha and Beta compete in segment X.",
    )
    set_session_active_worker("web:u:default", aid)
    reply = resolve_worker_followup("what did you find?", chat_key="web:u:default")
    assert reply and "Alpha" in reply

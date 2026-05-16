# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import link_registry_agent_to_runtime, record_agent_output, create_agent_task
from app.runtime.worker_operational_memory import list_deliverables_for_worker, persist_deliverable


def test_deliverable_survives_after_output() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="d1", name="writer", domain="marketing")
    aid = str(row["agent_id"])
    tid = create_agent_task(runtime_agent_id=aid, agent_handle="writer", prompt="research competitors")
    persist_deliverable(
        worker_id=aid,
        task_id=tid,
        deliverable_type="research_summary",
        summary="Competitor scan",
        content="Found 3 competitors.",
    )
    dels = list_deliverables_for_worker(aid)
    assert any(d.get("type") == "research_summary" for d in dels)

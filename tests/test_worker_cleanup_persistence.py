# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import link_registry_agent_to_runtime
from app.runtime.runtime_agents import set_runtime_agent_status
from app.runtime.worker_operational_memory import list_deliverables_for_worker, persist_deliverable


def test_deliverables_survive_worker_expiry() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="e1", name="expire_me", domain="general")
    aid = str(row["agent_id"])
    persist_deliverable(worker_id=aid, task_id="t1", deliverable_type="general_output", summary="x", content="y")
    set_runtime_agent_status(aid, "expired")
    assert list_deliverables_for_worker(aid)

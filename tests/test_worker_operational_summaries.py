# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import link_registry_agent_to_runtime
from app.services.worker_intelligence import build_worker_operational_summary


def test_worker_summary_has_specialization() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="s1", name="ops_bot", domain="ops")
    summ = build_worker_operational_summary(str(row["agent_id"]), row)
    assert summ.get("specialization") == "ops"

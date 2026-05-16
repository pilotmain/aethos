# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import persist_deliverable
from app.services.mission_control.worker_deliverable_ops import deliverable_trace_link


def test_deliverable_trace_chain() -> None:
    did = persist_deliverable(
        worker_id="wt1",
        task_id="tt1",
        deliverable_type="deployment_report",
        summary="trace test",
        content="x",
    )
    link = deliverable_trace_link(did, "wt1", "tt1")
    assert link["deliverable_id"] == did
    assert "deliverable" in link["chain"]

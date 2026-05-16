# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import persist_deliverable
from app.services.runtime_governance import build_governance_timeline


def test_timeline_includes_deliverable_kind() -> None:
    persist_deliverable(
        worker_id="tl1",
        task_id="t1",
        deliverable_type="repair_summary",
        summary="timeline repair",
        content="x",
    )
    tl = build_governance_timeline(limit=40)
    kinds = {e.get("kind") for e in tl.get("timeline") or []}
    assert "deliverable" in kinds or "repair" in kinds

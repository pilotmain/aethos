# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 44E — deterministic task prioritization."""

from __future__ import annotations

from app.services.autonomy.prioritize import prioritize_tasks
from app.services.tasks.unified_task import NexaTask


def test_prioritize_tasks_orders_by_priority_and_urgency() -> None:
    a = NexaTask(id="a", type="system", input="nice to have", priority=10, auto_generated=True, origin="x")
    b = NexaTask(id="b", type="dev", input="fix failing tests", priority=5, auto_generated=True, origin="x")
    c = NexaTask(id="c", type="dev", input="trivial", priority=90, auto_generated=True, origin="x")
    out = prioritize_tasks([a, b, c])
    assert out[0].id == "c"
    assert out[-1].id in ("a", "b")

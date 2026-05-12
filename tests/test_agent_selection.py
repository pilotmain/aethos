# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 47A — agent selection scores adapters using intel-shaped payloads."""

from __future__ import annotations

from app.services.agents.agent_selection import select_best_agent
from app.services.tasks.unified_task import NexaTask


def test_select_best_agent_prefers_high_performance() -> None:
    t = NexaTask(id="1", type="dev", input="fix pytest failures", context={}, priority=5, origin="x")
    agents = [
        {"handle": "local_stub", "performance_score": 0.4, "runs": 5},
        {"handle": "codex", "performance_score": 0.92, "runs": 12, "specialization": ["pytest"]},
    ]
    best = select_best_agent(t, agents)
    assert best is not None
    assert best.get("handle") == "codex"


def test_select_best_agent_returns_none_for_empty() -> None:
    t = NexaTask(id="1", type="system", input="x", context={}, priority=0, origin="x")
    assert select_best_agent(t, []) is None

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 47A — score agent candidates using persisted performance and task text."""

from __future__ import annotations

from typing import Any

from app.services.tasks.unified_task import NexaTask


def select_best_agent(task: NexaTask, agents: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Choose the best handle from ``agents`` (dicts with ``handle``, ``performance_score``,
    optional ``runs``, ``specialization`` list).
    """
    if not agents:
        return None
    blob = f"{task.input} {task.type}".lower()

    def rank(a: dict[str, Any]) -> float:
        base = float(a.get("performance_score") if a.get("performance_score") is not None else 0.5)
        runs = int(a.get("runs") or 0)
        if runs < 2:
            base *= 0.94
        for tag in a.get("specialization") or []:
            t = str(tag).lower()
            if t and t in blob:
                base += 0.1
        if runs >= 3 and base < 0.28:
            base *= 0.45
        return base

    return max(agents, key=rank)


__all__ = ["select_best_agent"]

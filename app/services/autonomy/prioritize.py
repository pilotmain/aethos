"""Phase 44 — deterministic prioritization shared by autonomy, scheduler hooks, and MC."""

from __future__ import annotations

from app.services.tasks.unified_task import NexaTask


def prioritize_tasks(tasks: list[NexaTask]) -> list[NexaTask]:
    """
    Sort tasks by explicit priority, failure urgency heuristics, and brevity tie-breakers.
    """

    def score(t: NexaTask) -> tuple[int, int, int]:
        urgency = 0
        blob = f"{t.input} {t.type}".lower()
        if any(x in blob for x in ("fix", "fail", "error", "block")):
            urgency += 25
        if t.type in ("dev", "scheduled"):
            urgency += 10
        if t.type == "mission":
            urgency += 5
        return (int(t.priority) + urgency, -len(t.input), hash(t.id) % 10_000)

    return sorted(tasks, key=score, reverse=True)


__all__ = ["prioritize_tasks"]

"""Phase 44 — deterministic prioritization shared by autonomy, scheduler hooks, and MC."""

from __future__ import annotations

from typing import Any

from app.services.tasks.unified_task import NexaTask


def prioritize_tasks(tasks: list[NexaTask], *, user_id: str | None = None) -> list[NexaTask]:
    """
    Sort tasks by explicit priority, failure urgency heuristics, and brevity tie-breakers.

    Phase 47 — optional ``user_id`` boosts goal-linked work using stored agent intel.
    """

    low_handles: set[str] = set()
    if user_id:
        try:
            from app.services.agents.agent_intel_store import list_agent_intel_profiles

            for p in list_agent_intel_profiles(user_id):
                h = str(p.get("handle") or "").strip().lower()
                runs = int(p.get("runs") or 0)
                score_pf = float(p.get("performance_score") or 0)
                if h and runs >= 3 and score_pf < 0.32:
                    low_handles.add(h)
        except Exception:
            low_handles = set()

    def score(t: NexaTask) -> tuple[int, int, int]:
        urgency = 0
        blob = f"{t.input} {t.type}".lower()
        if any(x in blob for x in ("fix", "fail", "error", "block")):
            urgency += 25
        if t.type in ("dev", "scheduled"):
            urgency += 10
        if t.type == "mission":
            urgency += 5
        if getattr(t, "goal_id", None):
            urgency += 20
        ctx: dict[str, Any] = t.context if isinstance(t.context, dict) else {}
        if ctx.get("goal_binding") or ctx.get("parent_goal_id"):
            urgency += 8
        suggested = str(ctx.get("suggested_agent") or "").strip().lower()
        if suggested and suggested in low_handles:
            urgency -= 12
        return (int(t.priority) + urgency, -len(t.input), hash(t.id) % 10_000)

    return sorted(tasks, key=score, reverse=True)


__all__ = ["prioritize_tasks"]

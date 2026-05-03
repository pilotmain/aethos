"""Optional per-request counters for verified provider/tool side-effects (extend later)."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass


@dataclass
class ExecutionTruthCounters:
    """Counts successful ``call_provider`` completions (non-local_stub)."""

    provider_side_effect_calls: int = 0


_cv: contextvars.ContextVar[ExecutionTruthCounters | None] = contextvars.ContextVar(
    "nexa_execution_truth_counters",
    default=None,
)


def reset_execution_truth_counters() -> None:
    _cv.set(ExecutionTruthCounters())


def get_execution_truth_counters() -> ExecutionTruthCounters:
    cur = _cv.get()
    if cur is None:
        cur = ExecutionTruthCounters()
        _cv.set(cur)
    return cur


def note_non_stub_provider_success(*, provider: str) -> None:
    """Call from outbound provider gateway when a real provider completes successfully."""
    if (provider or "").strip().lower() in ("local_stub", ""):
        return
    c = get_execution_truth_counters()
    c.provider_side_effect_calls += 1


__all__ = [
    "ExecutionTruthCounters",
    "get_execution_truth_counters",
    "note_non_stub_provider_success",
    "reset_execution_truth_counters",
]

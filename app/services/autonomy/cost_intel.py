"""Phase 46F — coarse cost estimation before executing autonomy / gateway work."""

from __future__ import annotations

from typing import Any

from app.services.tasks.unified_task import NexaTask


def predict_cost(task: NexaTask, *, provider: str = "anthropic") -> dict[str, Any]:
    """
    Rough upper-bound estimate — intended for budgeting UI, not billing.

    Uses input length heuristics; remote providers assume higher relative cost.
    """
    raw = f"{task.input} {task.context}".strip()
    est_tokens = min(32_000, max(400, len(raw) // 3 + 800))
    pl = (provider or "").strip().lower()
    usd_per_1k = 0.0 if pl in ("local_stub", "ollama", "") else 0.008
    est_usd = (est_tokens / 1000.0) * usd_per_1k
    return {
        "estimated_tokens": est_tokens,
        "estimated_usd": round(est_usd, 6),
        "provider_assumed": pl or "default",
    }


__all__ = ["predict_cost"]

"""Future: automated code review stage (Phase 23 placeholder)."""

from __future__ import annotations

from typing import Any


def reviewer_placeholder(*, goal: str, context: dict[str, Any]) -> dict[str, Any]:
    _ = goal, context
    return {"status": "skipped", "detail": "reviewer hook reserved for Phase 23+"}


__all__ = ["reviewer_placeholder"]

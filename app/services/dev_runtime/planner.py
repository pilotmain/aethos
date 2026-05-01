"""Deterministic dev plans (V1 — no external LLM)."""

from __future__ import annotations

from typing import Any

from app.models.dev_runtime import NexaDevWorkspace


def build_dev_plan(goal: str, workspace: NexaDevWorkspace) -> list[dict[str, Any]]:
    """
    Build a fixed pipeline: inspect → (bounded loop handled in service) → summary.

    Phase 25 runs adapter/test/fix iterations between inspect and summary.
    """
    _ = workspace
    g = (goal or "").strip()[:2000]
    return [
        {"type": "inspect", "description": "Inspect repository structure and git status"},
        {"type": "summary", "description": "Summarize run and PR-ready notes"},
    ]


__all__ = ["build_dev_plan"]

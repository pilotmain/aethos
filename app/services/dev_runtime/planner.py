"""Deterministic dev plans (V1 — no external LLM)."""

from __future__ import annotations

from typing import Any

from app.models.dev_runtime import NexaDevWorkspace


def build_dev_plan(goal: str, workspace: NexaDevWorkspace) -> list[dict[str, Any]]:
    """
    Build a fixed pipeline: inspect → test → coding agent → test → summary.

    ``goal`` and ``workspace`` influence descriptions only in V1.
    """
    _ = workspace
    g = (goal or "").strip()[:2000]
    return [
        {"type": "inspect", "description": "Inspect repository structure and git status"},
        {"type": "test", "description": f"Run tests ({g[:120]})"},
        {"type": "edit", "description": "Coding agent plan / artifact (stub)"},
        {"type": "test", "description": "Re-run tests after edits"},
        {"type": "summary", "description": "Summarize run and PR-ready notes"},
    ]


__all__ = ["build_dev_plan"]

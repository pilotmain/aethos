"""Deterministic dev plans (V1 — no external LLM)."""

from __future__ import annotations

from typing import Any

from app.models.dev_runtime import NexaDevWorkspace


def build_dev_plan(goal: str, workspace: NexaDevWorkspace) -> list[dict[str, Any]]:
    """
    Build a fixed pipeline: analyze → (bounded loop in service) → summary.

    The service loop implements **analyze → code → test → fix → repeat → commit**
    (bounded iterations); this plan supplies the upfront analyze + closing summary steps.
    """
    _ = workspace
    _ = (goal or "").strip()[:2000]
    return [
        {"type": "analyze", "description": "Analyze repository state and goal (git status, scope)"},
        {"type": "summary", "description": "Summarize run and PR-ready notes"},
    ]


__all__ = ["build_dev_plan"]

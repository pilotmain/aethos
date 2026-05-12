# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic dev plans (V1 — no external LLM)."""

from __future__ import annotations

from typing import Any

from app.models.dev_runtime import NexaDevWorkspace


def build_dev_plan(
    goal: str,
    workspace: NexaDevWorkspace,
    *,
    memory_notes: str | None = None,
) -> list[dict[str, Any]]:
    """
    Build a fixed pipeline: analyze → (bounded loop in service) → summary.

    The service loop implements **analyze → code → test → fix → repeat → commit**
    (bounded iterations); this plan supplies the upfront analyze + closing summary steps.
    """
    _ = workspace
    _ = (goal or "").strip()[:2000]
    mem = (memory_notes or "").strip()[:2000]
    analyze_desc = "Analyze repository state and goal (git status, scope)"
    if mem:
        analyze_desc = (
            f"{analyze_desc}. Consider saved user/project notes where relevant (bounded excerpt in run metadata)."
        )
    return [
        {"type": "analyze", "description": analyze_desc, "memory_notes_excerpt": bool(mem)},
        {"type": "summary", "description": "Summarize run and PR-ready notes"},
    ]


__all__ = ["build_dev_plan"]

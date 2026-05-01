"""PR preparation (V1 — summary text only, no GitHub API)."""

from __future__ import annotations

from typing import Any


def prepare_pr_summary(goal: str, result_json: dict[str, Any] | None) -> dict[str, Any]:
    """Produce a PR-ready summary blob for UI / export (no network)."""
    return {
        "title": (goal or "Dev mission")[:200],
        "body": "Automated dev run summary (Phase 24). Review tests and diffs locally before opening a PR.",
        "result_excerpt": str(result_json)[:4000] if result_json else "",
    }


__all__ = ["prepare_pr_summary"]

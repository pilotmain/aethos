"""PR preparation (V1 — summary text only, no GitHub API)."""

from __future__ import annotations

from typing import Any


def prepare_pr_summary(goal: str, result_json: dict[str, Any] | None) -> dict[str, Any]:
    """Produce a PR-ready summary blob for UI / export (no network)."""
    return {
        "title": (goal or "Dev mission")[:200],
        "body": "Automated dev run summary (Phase 25). Review tests and diffs locally before opening a PR.",
        "result_excerpt": str(result_json)[:4000] if result_json else "",
    }


def is_pr_ready(run_summary: dict[str, Any] | None) -> bool:
    """
    Heuristic PR readiness from persisted ``result_json`` — never implies merge/push.

    Requires passing tests, at least one changed path, and no recorded runtime/adapter hard failure.
    """
    if not run_summary:
        return False
    if not run_summary.get("tests_passed"):
        return False
    if run_summary.get("has_runtime_errors"):
        return False
    cf = run_summary.get("changed_files_end")
    if not isinstance(cf, list) or len(cf) == 0:
        return False
    return True


__all__ = ["prepare_pr_summary", "is_pr_ready"]

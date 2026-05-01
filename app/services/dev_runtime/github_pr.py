"""GitHub PR creation — stub until REST integration is approved (Phase 24)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def create_pull_request(
    *,
    goal: str,
    run_result: dict[str, Any] | None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Return a structured refusal + embedded summary (no network)."""
    from app.services.dev_runtime.pr import prepare_pr_summary

    s = get_settings()
    summary = prepare_pr_summary(goal, run_result or {})
    if workspace_id:
        summary = {**summary, "workspace_id": workspace_id}
    if not s.nexa_github_pr_enabled or not (s.github_token or "").strip():
        return {
            "ok": False,
            "reason": "GitHub PR API not enabled yet",
            "summary": summary,
        }
    return {
        "ok": False,
        "reason": "GitHub PR API not enabled yet",
        "summary": summary,
    }


__all__ = ["create_pull_request"]

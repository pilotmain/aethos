# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""CLI entry for automated GitHub PR review (calls in-process orchestrator)."""

from __future__ import annotations

import asyncio
import json
import sys


def cmd_pr_review(repo: str, pr_number: int) -> int:
    """Review ``owner/repo`` PR ``pr_number`` (requires ``GITHUB_TOKEN`` + enabled flags in ``.env``)."""
    from app.core.config import get_settings

    s = get_settings()
    if not s.nexa_pr_review_enabled:
        print(
            "Set NEXA_PR_REVIEW_ENABLED=true (and GITHUB_TOKEN) in .env — see docs/PR_REVIEW.md",
            file=sys.stderr,
        )
        return 1
    if "/" not in repo:
        print("repo must be owner/name", file=sys.stderr)
        return 2
    owner, name = repo.split("/", 1)

    async def _run() -> dict:
        from app.services.pr_review.orchestrator import PRReviewOrchestrator

        orch = PRReviewOrchestrator(owner, name)
        return await orch.review_pr(pr_number)

    result = asyncio.run(_run())
    print(json.dumps(result, indent=2, default=str))
    if not result.get("ok"):
        return 1
    summary = result.get("summary") or ""
    if summary:
        print("\n--- Summary ---\n", summary, sep="")
    return 0

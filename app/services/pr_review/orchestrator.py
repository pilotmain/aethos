"""
PR review orchestrator — GitHub fetch, static analysis, optional LLM, submit review.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.services.llm.base import Message
from app.services.llm.completion import primary_complete_messages
from app.services.pr_review.analyzer import PRAnalyzer, parse_ignore_patterns
from app.services.pr_review.github_client import GitHubPRClient

logger = logging.getLogger(__name__)

_MAX_INLINE_COMMENTS = 50


class PRReviewOrchestrator:
    """Coordinates GitHub API + analyzer + optional LLM + review submission."""

    def __init__(self, repo_owner: str, repo_name: str) -> None:
        self.settings = get_settings()
        token = (self.settings.github_token or "").strip()
        self._token_configured = bool(token)
        self.github = GitHubPRClient(token=token, repo_owner=repo_owner, repo_name=repo_name)
        patterns = parse_ignore_patterns(self.settings.nexa_pr_review_ignore_patterns)
        self.analyzer = PRAnalyzer(patterns)

    def _token_required_error(self) -> dict[str, Any]:
        return {"error": "GITHUB_TOKEN not configured", "ok": False}

    async def review_pr(self, pr_number: int) -> dict[str, Any]:
        if not self._token_configured:
            return self._token_required_error()

        logger.info("pr_review start number=%s repo=%s/%s", pr_number, self.github.repo_owner, self.github.repo_name)

        pr = await self.github.get_pr(pr_number)
        if not pr or pr.get("message") == "Not Found":
            return {"error": "PR not found", "ok": False}

        head = pr.get("head") or {}
        commit_sha = str(head.get("sha") or "")
        if not commit_sha:
            return {"error": "PR missing head.sha", "ok": False}

        files = await self.github.get_pr_files(pr_number)
        max_files = max(1, int(self.settings.nexa_pr_review_max_files))
        files = files[:max_files]

        all_issues: list[dict[str, Any]] = []

        for fmeta in files:
            fname = str(fmeta.get("filename") or "")
            if not fname or self.analyzer.should_ignore_file(fname):
                continue

            changes = int(fmeta.get("changes") or 0)
            if changes > 500:
                all_issues.append(
                    {
                        "path": fname,
                        "line": 1,
                        "message": f"Large diff ({changes} line changes) — consider splitting the PR",
                        "severity": "warning",
                        "suggestion": "Smaller PRs are easier to review and safer to merge.",
                    }
                )
                continue

            content = await self.github.get_file_content(fname, commit_sha)
            if content is None:
                continue

            patch = str(fmeta.get("patch") or "")
            file_issues = await self.analyzer.analyze_file(fname, patch, content)
            for issue in file_issues:
                issue["path"] = fname
            all_issues.extend(file_issues)

        if self.settings.use_real_llm:
            try:
                llm_feedback = await asyncio.to_thread(self._llm_feedback_sync, pr, files)
                all_issues.extend(llm_feedback)
            except Exception as exc:  # noqa: BLE001
                logger.warning("pr_review llm feedback failed: %s", exc)

        summary = await self.analyzer.generate_summary(all_issues)
        inline = await self.analyzer.generate_inline_comments(all_issues)
        inline = inline[:_MAX_INLINE_COMMENTS]

        has_blocking = any(str(i.get("severity")).lower() == "error" for i in all_issues)

        if self.settings.nexa_pr_review_auto_approve and not all_issues:
            await self.github.create_pull_request_review(
                pr_number,
                commit_id=commit_sha,
                body=summary,
                event="APPROVE",
            )
            return {
                "ok": True,
                "pr_number": pr_number,
                "action": "approved",
                "issues": all_issues,
                "summary": summary,
            }

        event = "REQUEST_CHANGES" if has_blocking else "COMMENT"
        await self.github.create_pull_request_review(
            pr_number,
            commit_id=commit_sha,
            body=summary,
            event=event,
            comments=inline or None,
        )

        return {
            "ok": True,
            "pr_number": pr_number,
            "action": "review_submitted",
            "review_event": event,
            "issues": all_issues,
            "summary": summary,
            "inline_comments": inline,
        }

    def _llm_feedback_sync(self, pr: dict[str, Any], files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pr_title = str(pr.get("title") or "")
        pr_body = str(pr.get("body") or "")
        changed_lines = "\n".join(
            f"- {f.get('filename')} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})"
            for f in files[:20]
        )
        prompt = f"""You are reviewing a pull request titled: "{pr_title}"

Description:
{pr_body[:1000]}

Changed files:
{changed_lines}

Provide brief feedback on:
1. Architectural concerns
2. Potential edge cases
3. Code duplication / testing gaps

Keep under 500 characters. If nothing stands out, reply exactly: No additional concerns."""
        messages = [Message(role="user", content=prompt)]
        response = primary_complete_messages(
            messages,
            temperature=0.3,
            max_tokens=512,
        )
        text = (response or "").strip()
        if not text or "No additional concerns" in text:
            return []
        return [
            {
                "path": "",
                "line": 0,
                "message": text,
                "severity": "info",
                "suggestion": "Optional LLM notes (verify against code)",
            }
        ]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""GitHub PR creation — REST when enabled; otherwise structured refusal (Phase 24–46)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.services.dev_runtime.git_tools import parse_github_slug_from_repo
from app.services.dev_runtime.pr import prepare_pr_summary


def create_pull_request(
    *,
    goal: str,
    run_result: dict[str, Any] | None,
    workspace_id: str | None = None,
    repo_path: Path | None = None,
    head_branch: str | None = None,
) -> dict[str, Any]:
    """Open a PR via GitHub REST when token + slug resolve; else return a safe refusal blob."""
    summary = prepare_pr_summary(goal, run_result or {})
    if workspace_id:
        summary = {**summary, "workspace_id": workspace_id}

    s = get_settings()
    token = (s.github_token or "").strip()
    if not s.nexa_github_pr_enabled or not token:
        return {
            "ok": False,
            "reason": "GitHub PR API not enabled or missing token",
            "summary": summary,
        }

    slug = parse_github_slug_from_repo(repo_path) if repo_path else None
    if not slug:
        return {
            "ok": False,
            "reason": "origin_remote_not_github_or_missing",
            "summary": summary,
        }

    owner, repo_name = slug
    base = (getattr(s, "nexa_github_default_branch", None) or "main").strip() or "main"
    head = (head_branch or "").strip()
    if not head:
        return {
            "ok": False,
            "reason": "missing_head_branch_for_pr",
            "summary": summary,
        }

    title = str(summary.get("title") or goal or "Nexa dev run")[:240]
    body = str(summary.get("body") or "Automated PR from Nexa dev mission.")[:60_000]
    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }
    ).encode("utf-8")

    req = Request(
        f"https://api.github.com/repos/{owner}/{repo_name}/pulls",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Nexa-Next-Phase46",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            return {
                "ok": True,
                "html_url": data.get("html_url"),
                "number": data.get("number"),
                "state": data.get("state"),
                "summary": summary,
            }
    except HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")[:4000]
        except Exception:
            err_body = str(exc)
        return {
            "ok": False,
            "reason": "github_http_error",
            "status": getattr(exc, "code", None),
            "detail": err_body,
            "summary": summary,
        }
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {
            "ok": False,
            "reason": "github_network_error",
            "detail": str(exc)[:2000],
            "summary": summary,
        }


__all__ = ["create_pull_request"]

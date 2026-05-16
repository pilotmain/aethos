# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Safe in-repo repair step execution (Phase 2 Step 6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.deploy_context.context_validation import workspace_confidence
from app.providers.repair.repair_verification import _run_shell, run_verification_suite


def _assert_repo_bound(repo: Path, deploy_ctx: dict[str, Any]) -> None:
    expected = Path(str(deploy_ctx.get("repo_path") or "")).resolve()
    if repo != expected:
        raise ValueError("repo_path_mismatch")


def preflight_repair(repo_path: str | Path, deploy_ctx: dict[str, Any]) -> dict[str, Any]:
    repo = Path(repo_path).resolve()
    _assert_repo_bound(repo, deploy_ctx)
    conf = workspace_confidence(repo)
    git_status = None
    if (repo / ".git").exists():
        r = _run_shell("git status --short", repo, timeout_sec=30.0)
        git_status = (r.get("cli") or {}).get("preview") if r.get("ok") else r.get("error")
    return {
        "repo_path": str(repo),
        "workspace_confidence": conf,
        "git_status_preview": git_status,
    }


def execute_repair_plan(
    plan: dict[str, Any],
    *,
    deploy_ctx: dict[str, Any],
) -> dict[str, Any]:
    """Execute inspect/shell/verify steps (not redeploy — caller handles that)."""
    repo = Path(str(deploy_ctx.get("repo_path") or "")).resolve()
    _assert_repo_bound(repo, deploy_ctx)
    pre = preflight_repair(repo, deploy_ctx)
    actions: list[dict[str, Any]] = []
    mutations: list[str] = []

    for step in plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        stype = str(step.get("type") or "")
        if stype == "inspect":
            target = str(step.get("target") or "package.json")
            p = repo / target
            actions.append({"type": "inspect", "target": target, "exists": p.is_file()})
            continue
        if stype == "shell":
            cmd = str(step.get("command") or "")
            row = _run_shell(cmd, repo)
            actions.append({"type": "shell", **row})
            if row.get("ok") and "install" in cmd:
                mutations.append("npm_install")
            if not row.get("ok"):
                return {
                    "ok": False,
                    "preflight": pre,
                    "actions": actions,
                    "mutations": mutations,
                    "blocked_reason": "shell_step_failed",
                }
            continue
        if stype == "verify":
            cmd = str(step.get("command") or "")
            row = _run_shell(cmd, repo)
            actions.append({"type": "verify", **row})
            if not row.get("ok"):
                return {
                    "ok": False,
                    "preflight": pre,
                    "actions": actions,
                    "mutations": mutations,
                    "blocked_reason": "verification_failed",
                    "failed_command": cmd,
                }
            continue
        if stype == "redeploy":
            actions.append({"type": "redeploy", "deferred": True})
            continue

    verify = run_verification_suite(repo)
    if not verify.get("ok"):
        return {
            "ok": False,
            "preflight": pre,
            "actions": actions,
            "mutations": mutations,
            "blocked_reason": "verification_suite_failed",
            "verification": verify,
        }
    return {
        "ok": True,
        "preflight": pre,
        "actions": actions,
        "mutations": mutations,
        "verification": verify,
    }

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Fix-and-redeploy operator summaries (Phase 2 Step 6)."""

from __future__ import annotations

from typing import Any


def render_fix_and_redeploy_success(
    *,
    project_id: str,
    repo_path: str,
    diagnosis: dict[str, Any],
    actions_taken: list[str],
    deploy_result: dict[str, Any],
) -> str:
    name = project_id.replace("-", " ").title()
    lines = [
        f"**{name} repair completed.**",
        "",
        "**Project:**",
        f"`{repo_path}`",
        "",
        "**Diagnosis:**",
        str(diagnosis.get("diagnosis") or diagnosis.get("failure_category") or "unknown"),
        "",
        "**Actions:**",
    ]
    for a in actions_taken[:12]:
        lines.append(f"- {a}")
    url = deploy_result.get("url")
    if url:
        lines.extend(["", "**Deployment:**", str(url)])
    elif deploy_result.get("summary"):
        lines.extend(["", "**Deployment:**", str(deploy_result.get("summary"))])
    return "\n".join(lines)


def render_fix_and_redeploy_blocked(
    *,
    project_id: str,
    repo_path: str | None,
    reason: str,
    diagnosis: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
    next_hint: str | None = None,
) -> str:
    name = project_id.replace("-", " ").title()
    lines = [
        f"I found **{name}** and inspected the workspace, but I did **not** redeploy.",
        "",
        "**Reason:**",
        reason,
    ]
    if repo_path:
        lines.extend(["", "**Project:**", f"`{repo_path}`"])
    if diagnosis:
        lines.extend(["", "**Diagnosis:**", str(diagnosis.get("diagnosis") or "")])
    if verification and verification.get("failed_command"):
        lines.extend(["", "**Failed command:**", f"`{verification['failed_command']}`"])
    hint = next_hint or f"Fix the issue locally, then ask:\nredeploy {project_id}"
    lines.extend(["", "**Next:**", hint])
    return "\n".join(lines)


__all__ = ["render_fix_and_redeploy_success", "render_fix_and_redeploy_blocked"]

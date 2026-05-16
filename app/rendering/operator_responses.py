# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Clean operator-facing copy for provider / deploy flows (Phase 2 Step 5)."""

from __future__ import annotations

from typing import Any

from app.deploy_context.errors import (
    DeploymentContextError,
    OperatorDeployError,
    ProjectResolutionError,
    ProviderAuthenticationError,
    ProviderCliMissingError,
    WorkspaceValidationError,
)


def _format_candidates(candidates: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, c in enumerate(candidates[:8], start=1):
        nm = str(c.get("name") or c.get("project_id") or "project")
        rp = str(c.get("repo_path") or "").strip()
        if rp:
            lines.append(f"{i}. {nm} — `{rp}`")
        else:
            lines.append(f"{i}. {nm}")
    return "\n".join(lines) if lines else "(none)"


def render_operator_deploy_error(exc: OperatorDeployError) -> str:
    if isinstance(exc, ProviderAuthenticationError):
        prov = str((exc.details or {}).get("provider") or "vercel")
        login = "vercel login" if prov == "vercel" else f"{prov} login"
        return (
            f"{prov.title()} CLI is installed but not authenticated.\n\n"
            f"Run once in your terminal:\n{login}\n\n"
            "Then:\naethos providers scan\n\n"
            "Then ask me again with the same request."
        )
    if isinstance(exc, ProviderCliMissingError):
        prov = str((exc.details or {}).get("provider") or "vercel")
        return (
            f"{prov.title()} CLI is not installed or not on PATH.\n\n"
            f"Install the {prov} CLI, then run:\naethos providers scan"
        )
    if isinstance(exc, ProjectResolutionError):
        cands = (exc.details or {}).get("candidates") or []
        block = _format_candidates(cands if isinstance(cands, list) else [])
        return (
            f"{exc.message}\n\n"
            f"Candidates:\n{block}\n\n"
            "Link one explicitly, for example:\n"
            "aethos projects link <slug> <absolute-path-to-repo-root>"
        )
    if isinstance(exc, WorkspaceValidationError):
        return f"{exc.message}\n\n" + "\n".join(f"• {s}" for s in (exc.suggestions or [])[:6])
    if isinstance(exc, DeploymentContextError):
        return f"{exc.message}\n\n" + "\n".join(f"• {s}" for s in (exc.suggestions or [])[:6])
    return exc.message


def render_provider_action_success(
    *,
    intent: str,
    project_id: str,
    provider: str,
    repo_path: str | None,
    result: dict[str, Any],
) -> str:
    action = str(result.get("action") or intent)
    summary = str(result.get("summary") or "").strip()
    url = result.get("url")
    dep_id = result.get("deployment_id")
    lines = [
        f"**{action.replace('_', ' ').title()}** for **{project_id}** via **{provider}**",
        "",
    ]
    if repo_path:
        lines.append(f"• Workspace: `{repo_path}`")
    if dep_id:
        lines.append(f"• Deployment: `{dep_id}`")
    if url:
        lines.append(f"• URL: {url}")
    if summary:
        lines.append(f"• {summary}")
    if result.get("success"):
        lines.append("\nDone.")
    else:
        extra = result.get("extra") or {}
        cli = extra.get("cli") if isinstance(extra, dict) else {}
        cat = cli.get("failure_category") if isinstance(cli, dict) else None
        if cat:
            lines.append(f"\nFailure category: `{cat}`")
        preview = cli.get("preview") if isinstance(cli, dict) else None
        if preview:
            lines.append(f"\n```\n{preview}\n```")
    return "\n".join(lines)


def render_privacy_blocked(reason: str | None = None) -> str:
    msg = reason or "Privacy policy blocked this provider operation."
    return f"**Privacy block**\n\n{msg}\n\nAdjust `AETHOS_PRIVACY_MODE` or redact sensitive content and try again."


def render_egress_blocked(reason: str | None = None) -> str:
    msg = reason or "External egress is blocked for this operation."
    return f"**Egress block**\n\n{msg}"


__all__ = [
    "render_operator_deploy_error",
    "render_provider_action_success",
    "render_privacy_blocked",
    "render_egress_blocked",
]

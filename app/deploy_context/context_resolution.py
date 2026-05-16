# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Resolve project slug → repo, provider link, and auth/CLI gates (Phase 2 Step 4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.deploy_context.context_validation import (
    require_package_json_or_pyproject,
    validate_repo_path,
    workspace_confidence,
)
from app.deploy_context.errors import (
    DeploymentContextError,
    ProjectResolutionError,
    ProviderAuthenticationError,
    ProviderCliMissingError,
)
from app.projects.project_discovery import discover_local_projects
from app.projects.project_registry_service import resolve_project_slug
from app.projects.vercel_link import read_vercel_project_link
from app.providers.provider_detection import detect_cli_path
from app.providers.provider_registry import get_provider_spec
from app.providers.provider_sessions import probe_provider_session
from app.runtime.runtime_state import (
    ensure_operator_context_schema,
    load_runtime_state,
    save_runtime_state,
    utc_now_iso,
)


def _format_candidates_block(candidates: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, c in enumerate(candidates[:8], start=1):
        rp = str(c.get("repo_path") or "").strip()
        nm = str(c.get("name") or c.get("project_id") or "").strip()
        if rp:
            lines.append(f"{i}. {nm} — {rp}")
        elif nm:
            lines.append(f"{i}. {nm}")
    return "\n".join(lines) if lines else "(none)"


def resolve_project_for_deploy(raw_name: str) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """
    Resolve slug to ``(project_id, project_row, candidates)``.

    Raises :class:`ProjectResolutionError` when ambiguous or unknown.
    """
    name = (raw_name or "").strip()
    if not name:
        raise ProjectResolutionError(
            "Missing project name.",
            suggestions=["Example: aethos deploy redeploy invoicepilot"],
        )
    pid, cands = resolve_project_slug(name)
    if pid and len(cands) == 1:
        return pid, cands[0], cands
    if not cands:
        discovered = discover_local_projects(max_candidates=40)
        fuzzy = [r for r in discovered if name.lower() in str(r.get("name", "")).lower() or name.lower() in str(r.get("project_id", "")).lower()]
        extra = fuzzy or discovered[:8]
        block = _format_candidates_block(extra)
        raise ProjectResolutionError(
            f"I could not find a registered project matching {name!r}.\n\n"
            f"Detected candidates:\n{block}\n\n"
            "Suggested action:\n"
            f"aethos projects link {name.lower()} <path-to-repo-root>",
            suggestions=["aethos projects scan", f"aethos projects link {name.lower()} <path>"],
            details={"candidates": extra},
        )
    block = _format_candidates_block(cands)
    raise ProjectResolutionError(
        f"Multiple projects match {name!r}. Pick one and link explicitly.\n\n{block}",
        suggestions=["aethos projects link <slug> <absolute-repo-path>"],
        details={"candidates": cands},
    )


def _pick_provider_link(row: dict[str, Any], want: str) -> dict[str, Any] | None:
    for link in row.get("provider_links") or []:
        if isinstance(link, dict) and str(link.get("provider") or "").lower() == want:
            return link
    return None


def build_deploy_context(
    project_slug: str,
    *,
    provider: str = "vercel",
    environment: str = "production",
) -> dict[str, Any]:
    """
    Build structured deploy context dict.

    Validates repo, markers, provider CLI + auth. Updates ``provider_resolution_cache`` on success.
    """
    prov = (provider or "vercel").strip().lower()
    env_target = (environment or "production").strip().lower() or "production"
    pid, row, _cands = resolve_project_for_deploy(project_slug)
    repo_raw = row.get("repo_path")
    if not repo_raw:
        raise DeploymentContextError(
            f"No linked repository path for project {pid!r}.",
            suggestions=[f"aethos projects link {pid} <absolute-path-to-repo-root>"],
            details={"project_id": pid},
        )
    repo = validate_repo_path(str(repo_raw))
    require_package_json_or_pyproject(repo)

    spec = get_provider_spec(prov)
    if not spec:
        raise DeploymentContextError(f"Unknown provider {prov!r}.", details={"provider": prov})

    cli_path = detect_cli_path(prov)
    if not cli_path:
        raise ProviderCliMissingError(
            f"{prov.title()} CLI is not installed or not on PATH.",
            suggestions=[f"Install the {prov} CLI, then: aethos providers scan"],
            details={"provider": prov},
        )

    s = get_settings()
    timeout = float(getattr(s, "aethos_provider_cli_timeout_sec", 20) or 20)
    sess = probe_provider_session(prov, timeout_sec=timeout)
    if not sess.get("authenticated"):
        raise ProviderAuthenticationError(
            f"{prov.title()} CLI is installed but not authenticated.",
            suggestions=[f"Run once: {prov} login", "Then: aethos providers scan"],
            details={"provider": prov, "cli_path": cli_path},
        )

    vlink = _pick_provider_link(row, prov) or read_vercel_project_link(repo)
    if prov == "vercel" and not vlink:
        raise DeploymentContextError(
            "No Vercel project link found for this repo (missing .vercel/project.json).",
            suggestions=["Run `vercel link` in the repo root, then: aethos providers scan"],
            details={"project_id": pid, "repo_path": str(repo)},
        )

    conf = workspace_confidence(repo)
    provider_project = None
    if isinstance(vlink, dict):
        provider_project = str(vlink.get("project_name") or vlink.get("project_id") or "").strip() or None

    ctx: dict[str, Any] = {
        "project_id": pid,
        "repo_path": str(repo),
        "provider": prov,
        "provider_project": provider_project,
        "workspace_valid": True,
        "package_json_present": (repo / "package.json").is_file(),
        "provider_authenticated": True,
        "provider_cli_installed": True,
        "resolved_by": "project_identity",
        "environment": env_target,
        "workspace_confidence": conf.get("workspace_confidence"),
        "confidence_signals": conf.get("signals") or [],
        "vercel_link": vlink if prov == "vercel" else None,
    }

    st = load_runtime_state()
    ensure_operator_context_schema(st)
    cache = st.setdefault("provider_resolution_cache", {})
    if isinstance(cache, dict):
        cache[pid] = {
            "provider": prov,
            "repo_path": str(repo),
            "last_verified_at": utc_now_iso(),
            "environment": env_target,
        }
        st["provider_resolution_cache"] = cache
        save_runtime_state(st)

    return ctx

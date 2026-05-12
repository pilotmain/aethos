# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Public entry: build a :class:`WorkspaceContextPack` for one turn."""

from __future__ import annotations

from pathlib import Path

from app.core.config import REPO_ROOT, get_settings
from app.services.workspace_intelligence.context_pack import build_pack
from app.services.workspace_intelligence.loader import resolve_workspace_root
from app.services.workspace_intelligence.schema import WorkspaceContextPack
from app.services.workspace_intelligence.selector import select_workspace_context


def workspace_intel_root_path() -> Path | None:
    s = get_settings()
    return resolve_workspace_root(getattr(s, "nexa_workspace_intel_root", ""), repo_root=REPO_ROOT)


def select_workspace_context_pack(
    user_text: str,
    *,
    project_slug: str | None = None,
) -> WorkspaceContextPack | None:
    """
    Load a bounded workspace context pack when the directory exists.

    Honors ``nexa_workspace_intel_default_token_budget`` from settings.
    """
    root = workspace_intel_root_path()
    if root is None:
        return None
    s = get_settings()
    budget = int(getattr(s, "nexa_workspace_intel_default_token_budget", 1500) or 1500)
    hard = int(getattr(s, "nexa_workspace_intel_hard_token_budget", 3000) or 3000)
    budget = max(200, min(budget, hard))

    ordered, skills = select_workspace_context(root, user_text, project_slug=project_slug)
    if not ordered:
        return WorkspaceContextPack(skills=skills, summary="", token_estimate=0)

    return build_pack(root, ordered, max_tokens=budget, skills=skills)


__all__ = ["select_workspace_context_pack", "workspace_intel_root_path"]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace intelligence — structured file-backed context without heavy infra."""

from __future__ import annotations

from app.services.workspace_intelligence.bundle import (
    select_workspace_context_pack,
    workspace_intel_root_path,
)
from app.services.workspace_intelligence.schema import WorkspaceContextPack
from app.services.workspace_intelligence.skills_graph import find_skill_chain

__all__ = [
    "WorkspaceContextPack",
    "find_skill_chain",
    "select_workspace_context_pack",
    "workspace_intel_root_path",
]

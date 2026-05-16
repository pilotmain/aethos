# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.projects.project_registry_service import link_project_repo, resolve_project_slug, scan_projects_registry
from app.projects.project_discovery import discover_local_projects

__all__ = [
    "discover_local_projects",
    "link_project_repo",
    "resolve_project_slug",
    "scan_projects_registry",
]

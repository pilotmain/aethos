# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight operator / workspace ownership summaries (Phase 3 Step 5)."""

from __future__ import annotations

from typing import Any


def build_operator_ownership_summary(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    """Who owns what — no full RBAC; clarity for teams."""
    op = truth.get("operator_context") or {}
    uid = (user_id or "").strip() or "runtime"
    providers = op.get("provider_ids") or []
    projects = op.get("project_registry") or {}
    project_rows = projects.get("projects") if isinstance(projects, dict) else projects
    project_count = len(project_rows) if isinstance(project_rows, dict) else 0
    deployments = (truth.get("deployments") or {}).get("identities") or {}
    return {
        "operator_id": uid,
        "runtime_owner": "AethOS Orchestrator",
        "workspace_root": (op.get("workspace") or {}).get("root") if isinstance(op.get("workspace"), dict) else None,
        "provider_ownership": [{"provider": p, "owner": uid} for p in providers[:12]],
        "deployment_count": len(deployments) if isinstance(deployments, dict) else 0,
        "project_count": project_count,
        "governance_actor": "operator",
    }

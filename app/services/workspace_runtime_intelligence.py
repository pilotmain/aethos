# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace / project runtime intelligence (Phase 3 Step 1)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.operator_context import build_operator_context_panel


def build_workspace_intelligence() -> dict[str, Any]:
    st = load_runtime_state()
    op = build_operator_context_panel()
    registry = op.get("project_registry") or st.get("project_registry") or {}
    projects = registry.get("projects") if isinstance(registry, dict) else {}
    identities = op.get("deployment_identities") or {}
    repairs = (st.get("repair_contexts") or {}).get("latest_by_project") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(projects, dict):
        for pid, row in list(projects.items())[:24]:
            if not isinstance(row, dict):
                continue
            ident = identities.get(pid) if isinstance(identities, dict) else None
            repair_id = repairs.get(pid) if isinstance(repairs, dict) else None
            rows.append(
                {
                    "project_id": pid,
                    "confidence": row.get("confidence") or row.get("repo_confidence"),
                    "deployment_linked": bool(ident),
                    "repair_active": bool(repair_id),
                    "provider": (ident or {}).get("provider") if isinstance(ident, dict) else None,
                    "verification_state": row.get("verification_state"),
                }
            )
    return {
        "projects": rows,
        "project_count": len(rows),
        "deployment_linked_count": sum(1 for r in rows if r.get("deployment_linked")),
        "repair_active_count": sum(1 for r in rows if r.get("repair_active")),
    }

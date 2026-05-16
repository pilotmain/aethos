# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Provider / project intelligence panel (Phase 3 Step 2)."""

from __future__ import annotations

from typing import Any

from app.services.operator_context import build_operator_context_panel
from app.services.workspace_runtime_intelligence import build_workspace_intelligence


def build_provider_intelligence_panel() -> dict[str, Any]:
    op = build_operator_context_panel()
    ws = build_workspace_intelligence()
    inventory = op.get("provider_inventory") or {}
    identities = op.get("deployment_identities") or {}
    repairs = op.get("latest_repair_contexts") or {}
    return {
        "provider_inventory": inventory,
        "provider_ids": op.get("provider_ids") or [],
        "project_registry": op.get("project_registry") or {},
        "deployment_identities": identities,
        "recent_provider_actions": (op.get("recent_provider_actions") or [])[-12:],
        "repair_history_summary": {
            "tracked_projects": len(repairs) if isinstance(repairs, dict) else 0,
        },
        "workspace": ws,
        "auth_status": _auth_status(inventory),
    }


def _auth_status(inventory: Any) -> dict[str, Any]:
    if not isinstance(inventory, dict):
        return {}
    out: dict[str, Any] = {}
    for pid, row in inventory.items():
        if isinstance(row, dict):
            out[str(pid)] = {
                "configured": bool(row.get("configured") or row.get("available")),
                "cli": row.get("cli") or row.get("tool"),
            }
    return out

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator-facing provider + project context (Mission Control JSON; additive)."""

from __future__ import annotations

from typing import Any

from app.providers.provider_registry import PROVIDER_IDS
from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state


def build_operator_context_panel() -> dict[str, Any]:
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    inv = st.get("provider_inventory") or {}
    pr = st.get("project_registry") or {}
    hist = st.get("project_resolution_history") or []
    if not isinstance(hist, list):
        hist = []
    providers = (inv.get("providers") or {}) if isinstance(inv, dict) else {}
    installed_ct = sum(1 for v in providers.values() if isinstance(v, dict) and v.get("cli_installed"))
    authed_ct = sum(1 for v in providers.values() if isinstance(v, dict) and v.get("authenticated"))
    projects = (pr.get("projects") or {}) if isinstance(pr, dict) else {}
    return {
        "provider_ids": list(PROVIDER_IDS),
        "provider_inventory": inv,
        "project_registry": pr,
        "summary": {
            "providers_installed": installed_ct,
            "providers_authenticated": authed_ct,
            "projects_tracked": len(projects) if isinstance(projects, dict) else 0,
        },
        "project_resolution_tail": hist[-12:],
    }

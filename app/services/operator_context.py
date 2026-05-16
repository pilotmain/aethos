# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator-facing provider + project context (Mission Control JSON; additive)."""

from __future__ import annotations

from typing import Any

from app.providers.provider_registry import PROVIDER_IDS
from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state


def _repair_mc_projection(row: dict[str, Any]) -> dict[str, Any]:
    bd = row.get("brain_decision") if isinstance(row.get("brain_decision"), dict) else {}
    ev = row.get("evidence_summary") if isinstance(row.get("evidence_summary"), dict) else {}
    return {
        **row,
        "brain_summary": {
            "provider": bd.get("selected_provider"),
            "model": bd.get("selected_model"),
            "reason": bd.get("reason"),
            "fallback_used": bd.get("fallback_used"),
        }
        if bd
        else None,
        "evidence_summary": ev or None,
        "verification_result": row.get("verification_result"),
        "blocked_redeploy_reason": row.get("blocked_reason"),
        "file_mutations": (
            (row.get("execution") or {}).get("mutations") if isinstance(row.get("execution"), dict) else None
        ),
        "privacy_findings": (ev.get("privacy") or {}).get("findings") if isinstance(ev.get("privacy"), dict) else None,
    }


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
    identities = st.get("deployment_identities") or {}
    if not isinstance(identities, dict):
        identities = {}
    cache = st.get("provider_resolution_cache") or {}
    if not isinstance(cache, dict):
        cache = {}
    actions = st.get("operator_provider_actions") or []
    if not isinstance(actions, list):
        actions = []
    nl_actions = [a for a in actions if isinstance(a, dict) and a.get("source") == "gateway_nl"]
    repair_store = st.get("repair_contexts") or {}
    latest_repairs: dict[str, Any] = {}
    if isinstance(repair_store, dict):
        lbp = repair_store.get("latest_by_project") or {}
        if isinstance(lbp, dict):
            for pid, rid in list(lbp.items())[:24]:
                bucket = repair_store.get(pid)
                if isinstance(bucket, dict) and isinstance(rid, str):
                    row = bucket.get(rid)
                    if isinstance(row, dict):
                        latest_repairs[pid] = _repair_mc_projection(row)
    last = actions[-1] if actions else {}
    last_nl = nl_actions[-1] if nl_actions else {}
    suggested: list[str] = []
    if isinstance(last, dict) and not last.get("success"):
        cat = str(last.get("failure_category") or "").strip()
        if cat == "missing_provider_auth":
            suggested.append("Run: vercel login")
            suggested.append("Then: aethos providers scan")
        elif cat in ("missing_provider_cli", "missing_workspace"):
            suggested.append("Run: aethos projects scan")
            suggested.append("Link repo: aethos projects link <slug> <path>")
    return {
        "provider_ids": list(PROVIDER_IDS),
        "provider_inventory": inv,
        "project_registry": pr,
        "deployment_identities": identities,
        "provider_resolution_cache": cache,
        "recent_provider_actions": actions[-24:],
        "recent_nl_provider_actions": nl_actions[-24:],
        "last_nl_provider_action": last_nl or None,
        "latest_repair_contexts": latest_repairs,
        "suggested_fixes": suggested,
        "summary": {
            "providers_installed": installed_ct,
            "providers_authenticated": authed_ct,
            "projects_tracked": len(projects) if isinstance(projects, dict) else 0,
            "deployment_links_tracked": len(identities),
            "resolution_cache_entries": len(cache),
        },
        "project_resolution_tail": hist[-12:],
    }

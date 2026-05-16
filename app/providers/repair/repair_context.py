# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persist repair contexts in runtime state (Phase 2 Step 6)."""

from __future__ import annotations

import uuid
from typing import Any

from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state, save_runtime_state, utc_now_iso


def _repair_store(st: dict[str, Any]) -> dict[str, Any]:
    ensure_operator_context_schema(st)
    rc = st.setdefault("repair_contexts", {})
    if not isinstance(rc, dict):
        rc = {}
        st["repair_contexts"] = rc
    return rc


def create_repair_context(
    *,
    project_id: str,
    deploy_ctx: dict[str, Any],
    diagnosis: dict[str, Any],
    logs_summary: str,
    source: str = "gateway_nl",
) -> dict[str, Any]:
    rid = str(uuid.uuid4())
    rec: dict[str, Any] = {
        "repair_context_id": rid,
        "project_id": project_id,
        "repo_path": deploy_ctx.get("repo_path"),
        "provider": deploy_ctx.get("provider"),
        "provider_project": deploy_ctx.get("provider_project"),
        "environment": deploy_ctx.get("environment") or "production",
        "failure_category": diagnosis.get("failure_category"),
        "logs_summary": (logs_summary or "")[:4000],
        "workspace_confidence": deploy_ctx.get("workspace_confidence"),
        "diagnosis": diagnosis,
        "source": source,
        "status": "open",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    st = load_runtime_state()
    store = _repair_store(st)
    by_project = store.setdefault(project_id, {})
    if not isinstance(by_project, dict):
        by_project = {}
        store[project_id] = by_project
    by_project[rid] = rec
    store["latest_by_project"] = store.get("latest_by_project") or {}
    if isinstance(store["latest_by_project"], dict):
        store["latest_by_project"][project_id] = rid
    save_runtime_state(st)
    return rec


def update_repair_context(project_id: str, repair_context_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    st = load_runtime_state()
    store = _repair_store(st)
    by_project = store.get(project_id) or {}
    if not isinstance(by_project, dict):
        return None
    cur = by_project.get(repair_context_id)
    if not isinstance(cur, dict):
        return None
    cur.update(patch)
    cur["updated_at"] = utc_now_iso()
    by_project[repair_context_id] = cur
    save_runtime_state(st)
    return cur


def list_repair_contexts(project_id: str) -> list[dict[str, Any]]:
    st = load_runtime_state()
    store = _repair_store(st)
    by_project = store.get(project_id) or {}
    if not isinstance(by_project, dict):
        return []
    return [v for v in by_project.values() if isinstance(v, dict) and v.get("repair_context_id")]


def get_latest_repair_context(project_id: str) -> dict[str, Any] | None:
    st = load_runtime_state()
    store = _repair_store(st)
    latest = (store.get("latest_by_project") or {}).get(project_id)
    if not latest:
        rows = list_repair_contexts(project_id)
        return rows[-1] if rows else None
    by_project = store.get(project_id) or {}
    if isinstance(by_project, dict):
        row = by_project.get(latest)
        return row if isinstance(row, dict) else None
    return None

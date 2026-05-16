# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from typing import Any

from app.projects.project_discovery import discover_local_projects
from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state, save_runtime_state, utc_now_iso


def scan_projects_registry(*, persist: bool = True) -> dict[str, Any]:
    rows = discover_local_projects()
    projects: dict[str, Any] = {}
    for row in rows:
        pid = str(row.get("project_id") or "").strip()
        if not pid:
            continue
        projects[pid] = {**row, "last_seen_at": utc_now_iso()}
    reg = {"projects": projects, "last_scanned_at": utc_now_iso()}
    if persist:
        st = load_runtime_state()
        ensure_operator_context_schema(st)
        st["project_registry"] = reg
        save_runtime_state(st)
    return reg


def link_project_repo(project_id: str, repo_path: str, *, persist: bool = True) -> dict[str, Any] | None:
    """Attach ``repo_path`` to a project entry (merge / upsert)."""
    pid = (project_id or "").strip().lower()
    if not pid:
        return None
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    pr = st.setdefault("project_registry", {})
    projects = pr.setdefault("projects", {})
    cur = projects.get(pid) or {
        "project_id": pid,
        "name": pid,
        "aliases": [pid],
        "provider_links": [],
        "detected_files": [],
    }
    cur["repo_path"] = str(repo_path).strip()
    cur["last_seen_at"] = utc_now_iso()
    projects[pid] = cur
    hist = st.setdefault("project_resolution_history", [])
    if isinstance(hist, list):
        hist.append({"ts": utc_now_iso(), "action": "link", "project_id": pid, "repo_path": cur["repo_path"]})
        st["project_resolution_history"] = hist[-200:]
    if persist:
        save_runtime_state(st)
    return cur


def resolve_project_slug(name: str) -> tuple[str | None, list[dict[str, Any]]]:
    """Return ``(project_id, candidates)`` for a fuzzy slug / alias match."""
    raw = (name or "").strip().lower()
    if not raw:
        return None, []
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    projects = (st.get("project_registry") or {}).get("projects") or {}
    if not isinstance(projects, dict):
        return None, []
    candidates: list[dict[str, Any]] = []
    for pid, row in projects.items():
        if not isinstance(row, dict):
            continue
        aliases = {str(a).lower() for a in (row.get("aliases") or []) if a}
        aliases.add(str(pid).lower())
        aliases.add(str(row.get("name") or "").lower())
        if raw == str(pid).lower() or raw in aliases:
            candidates.append(row)
    if len(candidates) == 1:
        return str(candidates[0].get("project_id") or ""), candidates
    if not candidates:
        for pid, row in projects.items():
            if isinstance(row, dict) and raw in str(row.get("repo_path") or "").lower():
                candidates.append(row)
    if len(candidates) == 1:
        return str(candidates[0].get("project_id") or ""), candidates
    return None, candidates[:12]

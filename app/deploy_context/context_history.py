# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persist operator provider action tail + deployment identity (Phase 2 Step 4)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state, save_runtime_state, utc_now_iso


def record_operator_provider_action(entry: dict[str, Any], *, persist: bool = True) -> None:
    """Append a redacted-safe action record (bounded list)."""
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    tail = st.setdefault("operator_provider_actions", [])
    if not isinstance(tail, list):
        tail = []
        st["operator_provider_actions"] = tail
    row = {**entry, "ts": entry.get("ts") or utc_now_iso()}
    tail.append(row)
    st["operator_provider_actions"] = tail[-100:]
    if persist:
        save_runtime_state(st)


def persist_deployment_identity(
    *,
    linked_project_id: str,
    provider: str,
    provider_project: str | None,
    deployment_id: str | None,
    environment: str,
    repo_path: str,
    url: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Store last-known deployment identity for a linked project."""
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    identities = st.setdefault("deployment_identities", {})
    if not isinstance(identities, dict):
        identities = {}
        st["deployment_identities"] = identities
    rec: dict[str, Any] = {
        "provider": provider,
        "provider_project": provider_project,
        "deployment_id": deployment_id,
        "environment": environment,
        "repo_path": repo_path,
        "linked_project_id": linked_project_id,
        "url": url,
        "updated_at": utc_now_iso(),
    }
    identities[linked_project_id] = rec
    if persist:
        save_runtime_state(st)
    return rec

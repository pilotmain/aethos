# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Governance search and filter (Phase 3 Step 13)."""

from __future__ import annotations

from typing import Any

from app.services.runtime_governance import build_governance_timeline


def _collect_entries(*, limit: int = 120) -> list[dict[str, Any]]:
    base = build_governance_timeline(limit=limit)
    return [e for e in (base.get("timeline") or []) if isinstance(e, dict)]


def _matches(entry: dict[str, Any], needle: str) -> bool:
    hay = " ".join(
        str(entry.get(k) or "")
        for k in ("what", "who", "kind", "provider", "actor", "severity", "project_id", "worker_id")
    ).lower()
    return needle in hay


def search_governance_entries(
    query: str | None = None,
    *,
    limit: int = 32,
    offset: int = 0,
) -> dict[str, Any]:
    entries = _collect_entries(limit=limit + offset + 64)
    q = (query or "").strip().lower()
    if q:
        entries = [e for e in entries if _matches(e, q)]
    page = entries[offset : offset + limit]
    return {
        "entries": page,
        "total": len(entries),
        "offset": offset,
        "limit": limit,
        "query": query,
    }


def filter_governance_entries(
    *,
    severity: str | None = None,
    actor: str | None = None,
    kind: str | None = None,
    provider: str | None = None,
    worker_id: str | None = None,
    deployment_id: str | None = None,
    category: str | None = None,
    limit: int = 32,
    offset: int = 0,
) -> dict[str, Any]:
    entries = _collect_entries(limit=limit + offset + 80)
    if severity:
        entries = [e for e in entries if str(e.get("severity") or "") == severity]
    if actor:
        a = actor.lower()
        entries = [e for e in entries if a in str(e.get("who") or "").lower()]
    if kind or category:
        k = (kind or category or "").lower()
        entries = [e for e in entries if str(e.get("kind") or "").lower() == k]
    if provider:
        p = provider.lower()
        entries = [e for e in entries if p in str(e.get("provider") or e.get("what") or "").lower()]
    if worker_id:
        w = worker_id.lower()
        entries = [e for e in entries if w in str(e.get("who") or e.get("worker_id") or "").lower()]
    if deployment_id:
        d = deployment_id.lower()
        entries = [e for e in entries if d in str(e.get("what") or e.get("deployment_id") or "").lower()]
    page = entries[offset : offset + limit]
    return {
        "entries": page,
        "total": len(entries),
        "offset": offset,
        "limit": limit,
        "filters": {
            "severity": severity,
            "actor": actor,
            "kind": kind or category,
            "provider": provider,
            "worker_id": worker_id,
            "deployment_id": deployment_id,
        },
    }

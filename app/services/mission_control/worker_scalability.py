# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Paginated worker summaries and scalability (Phase 3 Step 13)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.services.mission_control.runtime_worker_visibility import build_runtime_workers_view
from app.services.mission_control.runtime_scalability import build_worker_pressure_metrics


def list_worker_summaries(
    user_id: str | None = None,
    *,
    page: int = 1,
    page_size: int | None = None,
) -> dict[str, Any]:
    s = get_settings()
    size = page_size or int(getattr(s, "aethos_worker_summary_page_size", 24))
    size = max(1, min(size, 48))
    page = max(1, page)
    view = build_runtime_workers_view(user_id)
    workers = list(view.get("workers") or [])
    start = (page - 1) * size
    end = start + size
    page_rows = [
        {
            "agent_id": w.get("agent_id"),
            "handle": w.get("handle"),
            "role": w.get("role"),
            "status": w.get("status"),
            "summary": w.get("summary"),
            "memory_summary": str(w.get("memory_summary") or "")[:80],
        }
        for w in workers[start:end]
        if isinstance(w, dict)
    ]
    return {
        "workers": page_rows,
        "orchestrator": view.get("orchestrator"),
        "page": page,
        "page_size": size,
        "total": len(workers),
        "has_more": end < len(workers),
        "pressure": build_worker_pressure_metrics(),
    }

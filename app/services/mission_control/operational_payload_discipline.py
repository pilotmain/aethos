# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational payload caps, summarization, and discipline metrics (Phase 3 Step 13)."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso


def _payload_max_bytes() -> int:
    return int(getattr(get_settings(), "aethos_truth_payload_max_bytes", 400_000))


def _list_cap(key: str, items: list[Any] | None, cap: int) -> tuple[list[Any], int]:
    if not isinstance(items, list):
        return [], 0
    if len(items) <= cap:
        return items, 0
    return items[:cap], len(items) - cap


def summarize_truth_payload(truth: dict[str, Any]) -> dict[str, Any]:
    """Apply bounded caps and lightweight summaries to runtime truth."""
    out = dict(truth)
    collapsed = 0
    s = get_settings()
    deliv_cap = min(24, int(getattr(s, "aethos_worker_deliverable_limit", 200) // 8))
    event_cap = 32
    rec_cap = 10

    events, c = _list_cap("runtime_events", list(out.get("runtime_events") or []), event_cap)
    collapsed += c
    out["runtime_events"] = events

    deliverables, c = _list_cap("worker_deliverables", list(out.get("worker_deliverables") or []), deliv_cap)
    collapsed += c
    out["worker_deliverables"] = [_summarize_deliverable(d) for d in deliverables]

    conts, c = _list_cap("worker_continuations", list(out.get("worker_continuations") or []), 12)
    collapsed += c
    out["worker_continuations"] = conts

    recs = out.get("runtime_recommendations")
    if isinstance(recs, dict):
        items, c = _list_cap("recommendations", list(recs.get("recommendations") or []), rec_cap)
        collapsed += c
        out["runtime_recommendations"] = {**recs, "recommendations": items, "summarized": True}

    gov = out.get("runtime_governance")
    if isinstance(gov, dict):
        out["runtime_governance"] = _summarize_governance(gov)

    deploy = out.get("deployments")
    if isinstance(deploy, dict):
        ids = deploy.get("identities")
        if isinstance(ids, dict) and len(ids) > 16:
            keys = list(ids.keys())[:16]
            collapsed += len(ids) - 16
            deploy = {**deploy, "identities": {k: ids[k] for k in keys}, "identities_truncated": True}
            out["deployments"] = deploy

    workers = out.get("runtime_workers")
    if isinstance(workers, dict):
        wlist, c = _list_cap("workers", list(workers.get("workers") or []), 24)
        collapsed += c
        out["runtime_workers"] = {
            **workers,
            "workers": [_summarize_worker(w) for w in wlist],
            "summarized": True,
        }

    timeline = out.get("unified_operational_timeline")
    if isinstance(timeline, dict):
        entries, c = _list_cap("timeline", list(timeline.get("timeline") or timeline.get("entries") or []), 40)
        collapsed += c
        out["unified_operational_timeline"] = {**timeline, "timeline": entries, "summarized": True}

    approx = _approx_bytes(out)
    max_b = _payload_max_bytes()
    if approx > max_b:
        record_oversized_payload(approx_bytes=approx, max_bytes=max_b)
        out["_payload_trimmed"] = True

    record_payload_discipline(collapsed_sections=collapsed, approx_bytes=approx)
    return out


def _summarize_deliverable(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    return {
        "deliverable_id": row.get("deliverable_id") or row.get("id"),
        "worker_id": row.get("worker_id"),
        "type": row.get("type"),
        "summary": str(row.get("summary") or "")[:120],
        "status": row.get("status"),
        "created_at": row.get("created_at"),
        "project_id": row.get("project_id"),
        "detail_available": True,
    }


def _summarize_worker(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    return {
        "agent_id": row.get("agent_id"),
        "handle": row.get("handle"),
        "role": row.get("role"),
        "status": row.get("status"),
        "summary": row.get("summary"),
        "memory_summary": str(row.get("memory_summary") or "")[:80],
        "detail_available": True,
    }


def _summarize_governance(gov: dict[str, Any]) -> dict[str, Any]:
    out = dict(gov)
    for key in ("plugin_installs", "provider_operations", "privacy_enforcement", "repair_operations"):
        items, _ = _list_cap(key, list(out.get(key) or []), 8)
        out[key] = items
    out["summarized"] = True
    return out


def _approx_bytes(obj: Any) -> int:
    try:
        return len(json.dumps(obj, default=str))
    except (TypeError, ValueError):
        return 0


def get_payload_discipline_metrics() -> dict[str, Any]:
    st = load_runtime_state()
    m = st.get("payload_discipline_metrics") or {}
    return dict(m) if isinstance(m, dict) else {}


def record_payload_discipline(*, collapsed_sections: int, approx_bytes: int) -> None:
    st = load_runtime_state()
    m = st.setdefault("payload_discipline_metrics", {})
    if not isinstance(m, dict):
        m = {}
        st["payload_discipline_metrics"] = m
    prev = int(m.get("last_payload_bytes") or 0)
    m["last_payload_bytes"] = approx_bytes
    m["last_collapsed_sections"] = collapsed_sections
    m["updated_at"] = utc_now_iso()
    if prev and approx_bytes < prev:
        m["payload_reduction_rate"] = round((prev - approx_bytes) / max(1, prev), 4)
    elif prev and approx_bytes > prev:
        m["payload_growth_rate"] = round((approx_bytes - prev) / max(1, prev), 4)
    m["collapsed_payload_sections"] = int(m.get("collapsed_payload_sections") or 0) + collapsed_sections
    save_runtime_state(st)


def record_oversized_payload(*, approx_bytes: int, max_bytes: int) -> None:
    st = load_runtime_state()
    m = st.setdefault("payload_discipline_metrics", {})
    if isinstance(m, dict):
        m["oversized_payload_events"] = int(m.get("oversized_payload_events") or 0) + 1
        m["last_oversized_bytes"] = approx_bytes
        m["last_oversized_max"] = max_bytes
        m["updated_at"] = utc_now_iso()
    save_runtime_state(st)


def build_payload_discipline_block(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    m = get_payload_discipline_metrics()
    approx = _approx_bytes(truth) if truth else int(m.get("last_payload_bytes") or 0)
    return {
        "payload_bytes": approx,
        "payload_max_bytes": _payload_max_bytes(),
        "within_budget": approx <= _payload_max_bytes(),
        "collapsed_payload_sections": m.get("collapsed_payload_sections"),
        "oversized_payload_events": m.get("oversized_payload_events"),
        "payload_growth_rate": m.get("payload_growth_rate"),
        "payload_reduction_rate": m.get("payload_reduction_rate"),
        "timeline_summary_ratio": m.get("timeline_summary_ratio"),
    }

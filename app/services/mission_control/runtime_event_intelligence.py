# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Categorized runtime events with severity and correlation (Phase 2 Step 9)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_CATEGORIES = frozenset(
    {"runtime", "provider", "repair", "deployment", "brain", "privacy", "plugin", "workflow", "agent", "system"}
)
_SEVERITIES = frozenset({"info", "warning", "error", "critical"})

_EVENT_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "task_created": ("workflow", "info"),
    "task_started": ("workflow", "info"),
    "task_completed": ("workflow", "info"),
    "task_failed": ("workflow", "error"),
    "deployment_started": ("deployment", "info"),
    "deployment_completed": ("deployment", "info"),
    "deployment_failed": ("deployment", "error"),
    "deployment_rollback_started": ("deployment", "warning"),
    "agent_spawned": ("agent", "info"),
    "agent_suspended": ("agent", "warning"),
    "agent_expired": ("agent", "info"),
    "agent_recovered": ("agent", "info"),
    "brain_selected": ("brain", "info"),
    "provider_selected": ("provider", "info"),
    "repair_started": ("repair", "info"),
    "repair_verified": ("repair", "info"),
    "repair_redeploy_started": ("repair", "info"),
    "runtime_recovered": ("runtime", "info"),
    "queue_pressure": ("runtime", "warning"),
    "retry_pressure": ("runtime", "warning"),
    "privacy_redaction": ("privacy", "warning"),
    "privacy_block": ("privacy", "critical"),
    "plugin_loaded": ("plugin", "info"),
    "plugin_failed": ("plugin", "error"),
}

_MAX_BUFFER = 2500
_MAX_SUMMARY = 120


def infer_category_severity(event_type: str) -> tuple[str, str]:
    et = (event_type or "").strip()
    if et in _EVENT_CATEGORY_MAP:
        return _EVENT_CATEGORY_MAP[et]
    if "fail" in et or "error" in et:
        return "runtime", "error"
    if "block" in et or "pressure" in et:
        return "runtime", "warning"
    return "runtime", "info"


def normalize_runtime_event(
    event_type: str,
    *,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    category: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    cat, sev = infer_category_severity(event_type)
    cat = category if category in _CATEGORIES else cat
    sev = severity if severity in _SEVERITIES else sev
    cid = (correlation_id or "").strip() or str(uuid.uuid4())
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "category": cat,
        "severity": sev,
        "timestamp": utc_now_iso(),
        "correlation_id": cid,
        "payload": dict(payload or {}),
    }


def persist_runtime_event(row: dict[str, Any]) -> dict[str, Any]:
    st = load_runtime_state()
    buf = st.setdefault("runtime_event_buffer", [])
    if not isinstance(buf, list):
        buf = []
        st["runtime_event_buffer"] = buf
    buf.append(row)
    if len(buf) > _MAX_BUFFER:
        del buf[: len(buf) - _MAX_BUFFER]
    summaries = st.setdefault("runtime_event_summaries", [])
    if not isinstance(summaries, list):
        summaries = []
        st["runtime_event_summaries"] = summaries
    summaries.append(
        {
            "event_id": row.get("event_id"),
            "event_type": row.get("event_type"),
            "category": row.get("category"),
            "severity": row.get("severity"),
            "timestamp": row.get("timestamp"),
            "correlation_id": row.get("correlation_id"),
        }
    )
    if len(summaries) > _MAX_SUMMARY:
        del summaries[: len(summaries) - _MAX_SUMMARY]
    save_runtime_state(st)
    return row


def _coerce_event(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("event_type") and row.get("category"):
        return row
    et = str(row.get("event_type") or row.get("event") or row.get("mc_event_type") or "runtime_event")
    cat, sev = infer_category_severity(et)
    return {
        "event_id": row.get("event_id") or row.get("event_id"),
        "event_type": et,
        "category": row.get("category") or cat,
        "severity": row.get("severity") or sev,
        "timestamp": row.get("timestamp"),
        "correlation_id": row.get("correlation_id"),
        "payload": row.get("payload") if isinstance(row.get("payload"), dict) else {k: v for k, v in row.items() if k not in ("event", "event_type", "mc_event_type")},
    }


def list_normalized_events(*, limit: int = 80, category: str | None = None) -> list[dict[str, Any]]:
    st = load_runtime_state()
    buf = st.get("runtime_event_buffer") or []
    if not isinstance(buf, list):
        return []
    rows = [_coerce_event(r) for r in buf if isinstance(r, dict)]
    if category:
        rows = [r for r in rows if str(r.get("category") or "") == category]
    lim = max(1, min(int(limit), 500))
    return list(rows[-lim:])


def events_for_ws_replay(*, limit: int = 40) -> list[dict[str, Any]]:
    """Replay-safe tail for websocket reconnect."""
    return aggregate_events_for_display(limit=limit)


_SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2, "critical": 3}


def _severity_rank(sev: str | None) -> int:
    return _SEVERITY_ORDER.get(str(sev or "info"), 0)


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def filter_events_by_age(rows: list[dict[str, Any]], *, max_age_hours: float = 48.0) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    out: list[dict[str, Any]] = []
    for row in rows:
        ts = _parse_ts(str(row.get("timestamp") or ""))
        if ts is None or ts >= cutoff:
            out.append(row)
    return out


def prune_stale_event_summaries(*, max_age_hours: float = 72.0) -> int:
    st = load_runtime_state()
    summaries = st.get("runtime_event_summaries")
    if not isinstance(summaries, list):
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    kept = []
    for row in summaries:
        if not isinstance(row, dict):
            continue
        ts = _parse_ts(str(row.get("timestamp") or ""))
        if ts is None or ts >= cutoff:
            kept.append(row)
    removed = len(summaries) - len(kept)
    if removed:
        st["runtime_event_summaries"] = kept
        save_runtime_state(st)
    return removed


def prioritize_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Higher severity first, then newest timestamp."""
    return sorted(
        rows,
        key=lambda r: (_severity_rank(str(r.get("severity") or "")), str(r.get("timestamp") or "")),
        reverse=True,
    )


def aggregate_events_for_display(
    *,
    limit: int = 48,
    min_severity: str | None = None,
    category: str | None = None,
    categories: list[str] | None = None,
    suppress_info_when_noisy: bool = True,
) -> list[dict[str, Any]]:
    """
    Collapse repeated low-value events and return bounded summaries for Mission Control.
    """
    rows = filter_events_by_age(list_normalized_events(limit=min(500, limit * 4), category=category))
    if categories:
        allowed = {c.strip() for c in categories if c.strip()}
        rows = [r for r in rows if str(r.get("category") or "") in allowed]
    if min_severity:
        floor = _severity_rank(min_severity)
        rows = [r for r in rows if _severity_rank(str(r.get("severity") or "info")) >= floor]

    collapsed: dict[str, dict[str, Any]] = {}
    for row in rows:
        pl = row.get("payload")
        pid = pl.get("project_id", "") if isinstance(pl, dict) else ""
        key = f"{row.get('event_type')}|{row.get('category')}|{pid}"
        if key not in collapsed:
            collapsed[key] = {**row, "count": 1}
        else:
            collapsed[key]["count"] = int(collapsed[key].get("count") or 1) + 1
            collapsed[key]["timestamp"] = row.get("timestamp")
            if _severity_rank(str(row.get("severity"))) > _severity_rank(str(collapsed[key].get("severity"))):
                collapsed[key]["severity"] = row.get("severity")

    out = list(collapsed.values())
    if suppress_info_when_noisy:
        warn_plus = sum(1 for r in out if _severity_rank(str(r.get("severity"))) >= 1)
        if warn_plus >= 4:
            out = [r for r in out if _severity_rank(str(r.get("severity"))) >= 1 or int(r.get("count") or 1) > 2]
    out = prioritize_events(out)
    lim = max(1, min(int(limit), 120))
    result = out[:lim]
    try:
        from app.services.mission_control.runtime_metrics_discipline import record_event_collapse

        record_event_collapse(raw_count=len(rows), collapsed_count=len(result))
    except Exception:
        pass
    return result

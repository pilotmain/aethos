# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Long-run stability counters + operational reliability summary (OpenClaw parity lock)."""

from __future__ import annotations

from typing import Any

from app.orchestration import task_queue
from app.runtime.runtime_state import utc_now_iso


def default_runtime_stability() -> dict[str, Any]:
    return {
        "restart_cycles": 0,
        "successful_recoveries": 0,
        "failed_recoveries": 0,
        "retry_pressure_events": 0,
        "queue_pressure_events": 0,
        "deployment_pressure_events": 0,
        "runtime_degradation_events": 0,
        "updated_at": None,
    }


def ensure_runtime_stability_schema(st: dict[str, Any]) -> dict[str, Any]:
    base = default_runtime_stability()
    rs = st.setdefault("runtime_stability", dict(base))
    if not isinstance(rs, dict):
        st["runtime_stability"] = dict(base)
        rs = st["runtime_stability"]
    for k, v in base.items():
        if k == "updated_at":
            continue
        if k not in rs:
            rs[k] = v
        elif k != "updated_at" and not isinstance(rs.get(k), (int, float)):
            try:
                rs[k] = int(rs[k])
            except (TypeError, ValueError):
                rs[k] = v
    return st


def _stab(st: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_stability_schema(st)
    out = st["runtime_stability"]
    assert isinstance(out, dict)
    return out


def bump_stability_counter(st: dict[str, Any], key: str, delta: int = 1) -> None:
    if delta <= 0:
        return
    rs = _stab(st)
    rs[key] = int(rs.get(key) or 0) + int(delta)
    rs["updated_at"] = utc_now_iso()


def bump_restart_cycle(st: dict[str, Any]) -> None:
    bump_stability_counter(st, "restart_cycles", 1)


def bump_successful_recoveries(st: dict[str, Any], n: int = 1) -> None:
    bump_stability_counter(st, "successful_recoveries", n)


def bump_failed_recoveries(st: dict[str, Any], n: int = 1) -> None:
    bump_stability_counter(st, "failed_recoveries", n)


def bump_retry_pressure(st: dict[str, Any], n: int = 1) -> None:
    bump_stability_counter(st, "retry_pressure_events", n)


def bump_queue_pressure_stability(st: dict[str, Any], n: int = 1) -> None:
    bump_stability_counter(st, "queue_pressure_events", n)


def bump_deployment_pressure(st: dict[str, Any], n: int = 1) -> None:
    bump_stability_counter(st, "deployment_pressure_events", n)


def bump_runtime_degradation(st: dict[str, Any], n: int = 1) -> None:
    bump_stability_counter(st, "runtime_degradation_events", n)


_SEVERITY_ORDER = ("healthy", "warning", "degraded", "critical")


def _max_severity(a: str, b: str) -> str:
    ia = _SEVERITY_ORDER.index(a) if a in _SEVERITY_ORDER else 0
    ib = _SEVERITY_ORDER.index(b) if b in _SEVERITY_ORDER else 0
    return _SEVERITY_ORDER[max(ia, ib)]


def summarize_runtime_reliability(st: dict[str, Any]) -> dict[str, Any]:
    """Derive healthy / warning / degraded / critical from integrity, caps, and counters."""
    from app.core.config import get_settings
    from app.runtime.integrity.runtime_integrity import validate_runtime_state

    ensure_runtime_stability_schema(st)
    rs = dict(st.get("runtime_stability") or {})
    inv = validate_runtime_state(st)
    ok = bool(inv.get("ok"))
    ic = int(inv.get("issue_count") or 0)
    reasons: list[str] = []
    severity = "healthy"

    if not ok:
        reasons.append("integrity_issues")
        severity = "critical" if ic > 25 else "degraded" if ic > 5 else "warning"

    cfg = get_settings()
    sq = max(1, int(cfg.aethos_queue_limit))
    for qn in task_queue.QUEUE_NAMES:
        d = task_queue.queue_len(st, qn)
        if d >= max(1, int(sq * 0.95)):
            reasons.append(f"queue_near_cap:{qn}:{d}")
            severity = _max_severity(severity, "warning" if d < sq else "degraded")

    m = st.get("runtime_metrics") if isinstance(st.get("runtime_metrics"), dict) else {}
    rb = int(m.get("adaptive_retry_blocked_total") or 0)
    ex = int(m.get("retry_exhausted_total") or 0)
    if rb > 20 or ex > 20:
        reasons.append("retry_pressure_high")
        severity = _max_severity(severity, "warning")

    df = int(m.get("deployment_failed_total") or 0)
    if df > 10:
        reasons.append("deployment_failures_accumulated")
        severity = _max_severity(severity, "warning")

    qc = st.get("runtime_corruption_quarantine")
    qn = len(qc) if isinstance(qc, list) else 0
    if qn > 3:
        reasons.append("quarantine_backlog")
        severity = _max_severity(severity, "degraded" if qn > 8 else "warning")

    buf = st.get("runtime_event_buffer")
    bl = len(buf) if isinstance(buf, list) else 0
    belim = max(1, int(cfg.aethos_runtime_event_buffer_limit))
    if bl >= max(1, int(belim * 0.95)):
        reasons.append("runtime_event_buffer_pressure")
        severity = _max_severity(severity, "warning")

    severity_counts = {s: 0 for s in _SEVERITY_ORDER}
    severity_counts[severity] = 1

    return {
        "severity": severity,
        "reasons": reasons[:24],
        "stability_counters": rs,
        "severity_counts": severity_counts,
        "integrity_ok": ok,
        "integrity_issue_count": ic,
    }

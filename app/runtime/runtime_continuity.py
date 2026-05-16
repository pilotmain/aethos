# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Continuity counters and success rates for freeze / edge-case validation (read + small bumps)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import utc_now_iso


def default_runtime_continuity() -> dict[str, Any]:
    return {
        "continuity_failures": 0,
        "continuity_repairs": 0,
        "restart_recovery_attempts": 0,
        "restart_recovery_successes": 0,
        "deployment_recovery_attempts": 0,
        "deployment_recovery_successes": 0,
        "rollback_recovery_attempts": 0,
        "rollback_recovery_successes": 0,
        "updated_at": None,
    }


def ensure_runtime_continuity_schema(st: dict[str, Any]) -> dict[str, Any]:
    base = default_runtime_continuity()
    rc = st.setdefault("runtime_continuity", dict(base))
    if not isinstance(rc, dict):
        st["runtime_continuity"] = dict(base)
        rc = st["runtime_continuity"]
    for k, v in base.items():
        if k == "updated_at":
            continue
        if k not in rc:
            rc[k] = v
        elif k != "updated_at" and not isinstance(rc.get(k), (int, float)):
            try:
                rc[k] = int(rc[k])
            except (TypeError, ValueError):
                rc[k] = v
    return st


def _rc(st: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_continuity_schema(st)
    out = st["runtime_continuity"]
    assert isinstance(out, dict)
    return out


def bump_continuity_repairs(st: dict[str, Any], n: int = 1) -> None:
    if n <= 0:
        return
    rc = _rc(st)
    rc["continuity_repairs"] = int(rc.get("continuity_repairs") or 0) + int(n)
    rc["updated_at"] = utc_now_iso()


def bump_continuity_failures(st: dict[str, Any], n: int = 1) -> None:
    if n <= 0:
        return
    rc = _rc(st)
    rc["continuity_failures"] = int(rc.get("continuity_failures") or 0) + int(n)
    rc["updated_at"] = utc_now_iso()


def note_restart_recovery(st: dict[str, Any], *, success: bool) -> None:
    rc = _rc(st)
    rc["restart_recovery_attempts"] = int(rc.get("restart_recovery_attempts") or 0) + 1
    if success:
        rc["restart_recovery_successes"] = int(rc.get("restart_recovery_successes") or 0) + 1
    else:
        bump_continuity_failures(st, 1)
    rc["updated_at"] = utc_now_iso()


def note_deployment_recovery_batch(
    st: dict[str, Any],
    *,
    deployments_recovered: int,
    rollbacks_recovered: int,
) -> None:
    """Boot-time deployment/rollback recovery transitions (best-effort success when marked)."""
    rc = _rc(st)
    d = int(deployments_recovered)
    r = int(rollbacks_recovered)
    if d > 0:
        rc["deployment_recovery_attempts"] = int(rc.get("deployment_recovery_attempts") or 0) + d
        rc["deployment_recovery_successes"] = int(rc.get("deployment_recovery_successes") or 0) + d
    if r > 0:
        rc["rollback_recovery_attempts"] = int(rc.get("rollback_recovery_attempts") or 0) + r
        rc["rollback_recovery_successes"] = int(rc.get("rollback_recovery_successes") or 0) + r
    rc["updated_at"] = utc_now_iso()


def _rate(successes: int, attempts: int) -> float:
    if int(attempts) <= 0:
        return 1.0
    return round(min(1.0, float(int(successes)) / float(int(attempts))), 6)


def summarize_runtime_continuity(st: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_continuity_schema(st)
    rc = dict(st.get("runtime_continuity") or {})
    ra = int(rc.get("restart_recovery_attempts") or 0)
    rs = int(rc.get("restart_recovery_successes") or 0)
    da = int(rc.get("deployment_recovery_attempts") or 0)
    ds = int(rc.get("deployment_recovery_successes") or 0)
    ba = int(rc.get("rollback_recovery_attempts") or 0)
    bs = int(rc.get("rollback_recovery_successes") or 0)
    return {
        **rc,
        "restart_recovery_success_rate": _rate(rs, ra),
        "deployment_recovery_success_rate": _rate(ds, da),
        "rollback_recovery_success_rate": _rate(bs, ba),
    }

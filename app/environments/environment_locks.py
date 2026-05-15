# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Per-environment deployment locks (OpenClaw continuity — prevent concurrent deploys)."""

from __future__ import annotations

from typing import Any

from app.deployments.deployment_registry import get_deployment
from app.deployments.deployment_stages import is_terminal_stage
from app.environments import environment_registry
from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import utc_now_iso


def locks_map(st: dict[str, Any]) -> dict[str, Any]:
    d = st.setdefault("environment_locks", {})
    if not isinstance(d, dict):
        st["environment_locks"] = {}
        return st["environment_locks"]
    return d


def get_lock(st: dict[str, Any], environment_id: str) -> dict[str, Any] | None:
    row = locks_map(st).get(str(environment_id))
    return row if isinstance(row, dict) else None


def acquire_lock(
    st: dict[str, Any],
    environment_id: str,
    deployment_id: str,
    *,
    user_id: str = "",
    lock_status: str = "deploying",
) -> bool:
    """Return True if this deployment holds (or re-acquires) the lock."""
    eid = str(environment_id).strip()
    did = str(deployment_id).strip()
    if not eid or not did:
        return False
    environment_registry.ensure_environment(st, eid, user_id=str(user_id or ""))
    cur = get_lock(st, eid)
    if cur and str(cur.get("locked_by_deployment_id") or "") not in ("", did):
        return False
    ts = utc_now_iso()
    rec = {
        "environment_id": eid,
        "locked_by_deployment_id": did,
        "locked_at": ts,
        "lock_reason": "deployment",
        "status": str(lock_status)[:64],
        "user_id": str(user_id or ""),
    }
    locks_map(st)[eid] = rec
    orchestration_log.append_json_log(
        "environments",
        "deployment_lock_acquired",
        environment_id=eid,
        deployment_id=did,
    )
    emit_runtime_event(
        st,
        "deployment_lock_acquired",
        environment_id=eid,
        deployment_id=did,
        user_id=str(user_id or ""),
    )
    return True


def release_lock(st: dict[str, Any], environment_id: str, deployment_id: str) -> bool:
    eid = str(environment_id).strip()
    did = str(deployment_id).strip()
    cur = get_lock(st, eid)
    if not cur or str(cur.get("locked_by_deployment_id") or "") != did:
        return False
    locks_map(st).pop(eid, None)
    orchestration_log.append_json_log(
        "environments",
        "deployment_lock_released",
        environment_id=eid,
        deployment_id=did,
    )
    emit_runtime_event(
        st,
        "deployment_lock_released",
        environment_id=eid,
        deployment_id=did,
    )
    return True


def list_locks_for_user(st: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    out: list[dict[str, Any]] = []
    for _eid, lk in locks_map(st).items():
        if not isinstance(lk, dict):
            continue
        if uid and str(lk.get("user_id") or "") != uid:
            continue
        out.append(dict(lk))
    out.sort(key=lambda r: str(r.get("locked_at") or ""), reverse=True)
    return out


def repair_stale_locks(st: dict[str, Any]) -> dict[str, Any]:
    """Clear locks whose deployment is terminal (unless mid-rollback). Backup once before any mutation."""
    to_pop: list[str] = []
    to_release: list[tuple[str, str]] = []
    for eid, lk in list(locks_map(st).items()):
        if not isinstance(lk, dict):
            to_pop.append(str(eid))
            continue
        did = str(lk.get("locked_by_deployment_id") or "")
        if not did:
            to_pop.append(str(eid))
            continue
        dep = get_deployment(st, did)
        if not isinstance(dep, dict):
            to_pop.append(str(eid))
            continue
        rb = dep.get("rollback") if isinstance(dep.get("rollback"), dict) else {}
        rb_running = str(rb.get("status") or "") == "running"
        stg = str(dep.get("deployment_stage") or "")
        stat = str(dep.get("status") or "")
        terminal = is_terminal_stage(stg) or stat in ("completed", "failed", "rolled_back", "cancelled")
        if terminal and not rb_running:
            to_release.append((str(eid), did))
    n = len(to_pop) + len(to_release)
    if n:
        try:
            from app.runtime.backups.runtime_backups import backup_runtime_state_dict

            backup_runtime_state_dict(st, reason="environment_lock_repair")
        except Exception:
            pass
    for eid in to_pop:
        locks_map(st).pop(eid, None)
    fixes = len(to_pop)
    for eid, did in to_release:
        if release_lock(st, eid, did):
            fixes += 1
    if fixes:
        orchestration_log.append_json_log(
            "deployment_recovery",
            "environment_locks_repaired",
            fixes=fixes,
        )
    return {"locks_repaired": fixes}

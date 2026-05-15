# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Canonical ``~/.aethos/aethos.json`` read/write with atomic replace."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.paths import get_aethos_workspace_root, get_runtime_state_path

_LOG = logging.getLogger("aethos.runtime")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now_iso() -> str:
    """ISO-8601 UTC timestamp for runtime JSON fields."""
    return _utc_now()


def default_runtime_state(*, workspace_root: Path | None = None) -> dict[str, Any]:
    ws = workspace_root or get_aethos_workspace_root()
    return {
        "runtime_id": str(uuid.uuid4()),
        "created_at": _utc_now(),
        "last_started_at": None,
        "gateway": {
            "host": "0.0.0.0",
            "port": int(os.environ.get("AETHOS_RUNTIME_PORT") or os.environ.get("PORT") or "8010"),
            "running": False,
            "pid": None,
            "last_heartbeat": None,
        },
        "workspace": {"root": str(ws.resolve())},
        "sessions": [],
        "agents": [],
        "deployments": [],
        "channels": [],
        "tasks": [],
        "execution_queue": [],
        "long_running": [],
        "memory": {"enabled": True},
        "recovery": {"events": []},
        # --- OpenClaw orchestration runtime parity (Phase 1; JSON until DB-backed) ---
        "task_registry": {},
        "deployment_queue": [],
        "agent_queue": [],
        "channel_queue": [],
        "recovery_queue": [],
        "scheduler_queue": [],
        "orchestration": {
            "scheduler": {
                "enabled": True,
                "running": False,
                "last_tick": None,
                "ticks": 0,
                "last_error": None,
            },
            "checkpoints": {},
        },
        # --- OpenClaw autonomous execution parity (Phase 1; JSON until DB-backed) ---
        "execution": {
            "plans": {},
            "chains": {},
            "checkpoints": {},
            "memory": {},
            "supervisor": {
                "ticks": 0,
                "last_tick": None,
                "last_error": None,
            },
        },
        "runtime_sessions": {},
        "runtime_event_buffer": [],
        "deployment_records": {},
        "environments": {},
        "operational_workflows": [],
        "deployment_scheduler": {"pending": [], "locks": {}},
        "environment_locks": {},
        "runtime_metrics": {
            "scheduler_ticks": 0,
            "last_scheduler_tick_at": None,
            "queue_dispatch_total": 0,
            "tasks_completed_total": 0,
            "tasks_failed_total": 0,
            "runtime_boot_count": 0,
            "deployment_started_total": 0,
            "deployment_completed_total": 0,
            "deployment_failed_total": 0,
            "rollback_started_total": 0,
            "rollback_completed_total": 0,
            "deployment_recovery_boot_total": 0,
            "environment_recovery_boot_total": 0,
            "operational_workflow_total": 0,
            "coordination_active_agents": 0,
            "coordination_delegations_total": 0,
            "coordination_policy_assignments_total": 0,
            "coordination_autonomous_loops": 0,
            "coordination_supervisor_restarts": 0,
            "coordination_recovery_loops": 0,
            "planning_generated_total": 0,
            "replanning_total": 0,
            "optimization_cycles_total": 0,
            "adaptive_retry_total": 0,
            "reasoning_cycles_total": 0,
            "optimization_success_total": 0,
            "runtime_backups_total": 0,
            "runtime_corruption_repairs_total": 0,
            "queue_dedupe_total": 0,
        },
        "coordination_agents": {},
        "agent_delegations": {},
        "autonomous_loops": [],
        "runtime_supervisors": {},
        "planning_records": {},
        "planning_outcomes": [],
        "runtime_resilience": {},
        "runtime_corruption_quarantine": [],
    }


def ensure_execution_schema(st: dict[str, Any]) -> dict[str, Any]:
    """Merge missing autonomous execution keys (forward-compatible)."""
    base = default_runtime_state()
    ex = st.setdefault("execution", base.get("execution"))
    if not isinstance(ex, dict):
        st["execution"] = dict(base["execution"])
        ex = st["execution"]
    for key in ("plans", "chains", "checkpoints", "memory"):
        if key not in ex or not isinstance(ex.get(key), dict):
            ex[key] = {}
    sup = ex.setdefault("supervisor", {})
    if not isinstance(sup, dict):
        ex["supervisor"] = dict(base["execution"]["supervisor"])
    else:
        for k, v in (base["execution"]["supervisor"] or {}).items():
            sup.setdefault(k, v)
    return st


def ensure_orchestration_schema(st: dict[str, Any]) -> dict[str, Any]:
    """Merge missing orchestration keys onto loaded ``aethos.json`` (forward-compatible)."""
    base = default_runtime_state()
    for key in (
        "task_registry",
        "deployment_queue",
        "agent_queue",
        "channel_queue",
        "recovery_queue",
        "scheduler_queue",
        "orchestration",
    ):
        if key not in st:
            st[key] = base[key]  # type: ignore[index]
    orch = st.setdefault("orchestration", {})
    if not isinstance(orch, dict):
        st["orchestration"] = base["orchestration"]
        orch = st["orchestration"]
    sch = orch.setdefault("scheduler", {})
    if not isinstance(sch, dict):
        orch["scheduler"] = dict(base["orchestration"]["scheduler"])
    else:
        for k, v in (base["orchestration"]["scheduler"] or {}).items():
            sch.setdefault(k, v)
    orch.setdefault("checkpoints", {})
    if not isinstance(orch.get("checkpoints"), dict):
        orch["checkpoints"] = {}
    tr = st.setdefault("task_registry", {})
    if not isinstance(tr, dict):
        st["task_registry"] = {}
    for qn in (
        "execution_queue",
        "deployment_queue",
        "agent_queue",
        "channel_queue",
        "recovery_queue",
        "scheduler_queue",
    ):
        if qn not in st or not isinstance(st.get(qn), list):
            st[qn] = []
    return st


def ensure_deployment_environment_schema(st: dict[str, Any]) -> dict[str, Any]:
    """Merge deployment + environment runtime keys (OpenClaw infra ops parity)."""
    base = default_runtime_state()
    if "deployment_records" not in st or not isinstance(st.get("deployment_records"), dict):
        st["deployment_records"] = dict(base.get("deployment_records") or {})
    if "environments" not in st or not isinstance(st.get("environments"), dict):
        st["environments"] = dict(base.get("environments") or {})
    if "operational_workflows" not in st or not isinstance(st.get("operational_workflows"), list):
        st["operational_workflows"] = list(base.get("operational_workflows") or [])
    if "environment_locks" not in st or not isinstance(st.get("environment_locks"), dict):
        st["environment_locks"] = dict(base.get("environment_locks") or {})
    ds = st.setdefault("deployment_scheduler", base.get("deployment_scheduler") or {})
    if not isinstance(ds, dict):
        st["deployment_scheduler"] = dict(base["deployment_scheduler"])
        ds = st["deployment_scheduler"]
    ds.setdefault("pending", [])
    ds.setdefault("locks", {})
    if not isinstance(ds.get("pending"), list):
        ds["pending"] = []
    if not isinstance(ds.get("locks"), dict):
        ds["locks"] = {}
    m = st.setdefault("runtime_metrics", base.get("runtime_metrics") or {})
    if not isinstance(m, dict):
        st["runtime_metrics"] = dict(base["runtime_metrics"])
        m = st["runtime_metrics"]
    for k, v in (base.get("runtime_metrics") or {}).items():
        m.setdefault(k, v)
    return st


def ensure_agent_coordination_schema(st: dict[str, Any]) -> dict[str, Any]:
    """Merge autonomous multi-agent coordination keys (OpenClaw parity)."""
    base = default_runtime_state()
    ca = st.setdefault("coordination_agents", base.get("coordination_agents") or {})
    if not isinstance(ca, dict):
        st["coordination_agents"] = {}
    ad = st.setdefault("agent_delegations", base.get("agent_delegations") or {})
    if not isinstance(ad, dict):
        st["agent_delegations"] = {}
    al = st.setdefault("autonomous_loops", base.get("autonomous_loops") or [])
    if not isinstance(al, list):
        st["autonomous_loops"] = []
    rs = st.setdefault("runtime_supervisors", base.get("runtime_supervisors") or {})
    if not isinstance(rs, dict):
        st["runtime_supervisors"] = {}
    m = st.setdefault("runtime_metrics", base.get("runtime_metrics") or {})
    if not isinstance(m, dict):
        st["runtime_metrics"] = dict(base["runtime_metrics"])
        m = st["runtime_metrics"]
    for k, v in (base.get("runtime_metrics") or {}).items():
        m.setdefault(k, v)
    return st


def ensure_planning_intelligence_schema(st: dict[str, Any]) -> dict[str, Any]:
    """Merge adaptive planning + intelligence runtime keys (OpenClaw parity)."""
    base = default_runtime_state()
    pr = st.setdefault("planning_records", base.get("planning_records") or {})
    if not isinstance(pr, dict):
        st["planning_records"] = {}
    po = st.setdefault("planning_outcomes", base.get("planning_outcomes") or [])
    if not isinstance(po, list):
        st["planning_outcomes"] = []
    m = st.setdefault("runtime_metrics", base.get("runtime_metrics") or {})
    if not isinstance(m, dict):
        st["runtime_metrics"] = dict(base["runtime_metrics"])
        m = st["runtime_metrics"]
    for k, v in (base.get("runtime_metrics") or {}).items():
        m.setdefault(k, v)
    return st


def ensure_resilience_schema(st: dict[str, Any]) -> dict[str, Any]:
    """Merge resilience / quarantine keys (OpenClaw recovery hardening parity)."""
    base = default_runtime_state()
    rs = st.setdefault("runtime_resilience", base.get("runtime_resilience") or {})
    if not isinstance(rs, dict):
        st["runtime_resilience"] = {}
    cq = st.setdefault("runtime_corruption_quarantine", base.get("runtime_corruption_quarantine") or [])
    if not isinstance(cq, list):
        st["runtime_corruption_quarantine"] = []
    m = st.setdefault("runtime_metrics", base.get("runtime_metrics") or {})
    if not isinstance(m, dict):
        st["runtime_metrics"] = dict(base["runtime_metrics"])
        m = st["runtime_metrics"]
    for k, v in (base.get("runtime_metrics") or {}).items():
        m.setdefault(k, v)
    return st


def ensure_multi_session_schema(st: dict[str, Any]) -> dict[str, Any]:
    """Merge OpenClaw multi-session + runtime event buffers (forward-compatible)."""
    base = default_runtime_state()
    rs = st.setdefault("runtime_sessions", base.get("runtime_sessions") or {})
    if not isinstance(rs, dict):
        st["runtime_sessions"] = {}
    buf = st.setdefault("runtime_event_buffer", base.get("runtime_event_buffer") or [])
    if not isinstance(buf, list):
        st["runtime_event_buffer"] = []
    m = st.setdefault("runtime_metrics", base.get("runtime_metrics") or {})
    if not isinstance(m, dict):
        st["runtime_metrics"] = dict(base["runtime_metrics"])
    else:
        for k, v in (base.get("runtime_metrics") or {}).items():
            m.setdefault(k, v)
    return st


def load_runtime_state() -> dict[str, Any]:
    path = get_runtime_state_path()
    if not path.is_file():
        st = default_runtime_state()
        save_runtime_state(st)
        return st
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _LOG.warning("runtime_state.json_corrupt %s — quarantine + reset", exc)
        from app.runtime.corruption.runtime_corruption import quarantine_corrupt_runtime_file

        quarantine_corrupt_runtime_file(path, reason=f"json_decode:{exc}")
        st = default_runtime_state()
        save_runtime_state(st)
        return st
    except OSError as exc:
        _LOG.warning("runtime_state.read_failed %s — resetting", exc)
        st = default_runtime_state()
        save_runtime_state(st)
        return st
    try:
        if not isinstance(data, dict):
            raise ValueError("root must be object")
        ensure_orchestration_schema(data)
        ensure_execution_schema(data)
        ensure_multi_session_schema(data)
        ensure_deployment_environment_schema(data)
        ensure_agent_coordination_schema(data)
        ensure_planning_intelligence_schema(data)
        from app.runtime.corruption.runtime_repair import repair_runtime_queues_and_metrics

        repaired = repair_runtime_queues_and_metrics(data)
        if int(repaired.get("queues_coerced") or 0) or int(repaired.get("metrics_coerced") or 0):
            m = data.setdefault("runtime_metrics", {})
            if isinstance(m, dict):
                m["runtime_corruption_repairs_total"] = int(m.get("runtime_corruption_repairs_total") or 0) + 1
        ensure_resilience_schema(data)
        return data
    except Exception as exc:
        _LOG.warning("runtime_state.load_failed %s — resetting", exc)
        st = default_runtime_state()
        save_runtime_state(st)
        return st


def save_runtime_state(data: dict[str, Any]) -> None:
    path = get_runtime_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd: int | None = None
    try:
        import fcntl

        lock_fd = os.open(str(path.parent / "aethos.json.write.lock"), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except Exception:
        lock_fd = None
    payload = json.dumps(data, indent=2, sort_keys=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="aethos-runtime-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    finally:
        if lock_fd is not None:
            try:
                import fcntl

                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except Exception:
                pass


def mark_gateway_stopped() -> None:
    try:
        st = load_runtime_state()
        gw = st.setdefault("gateway", {})
        gw["running"] = False
        gw["pid"] = None
        gw["last_heartbeat"] = _utc_now()
        save_runtime_state(st)
    except Exception as exc:
        _LOG.warning("runtime_state.mark_stopped_failed %s", exc)


def record_recovery_event(st: dict[str, Any], message: str) -> None:
    rec = st.setdefault("recovery", {})
    ev = rec.setdefault("events", [])
    if not isinstance(ev, list):
        ev = []
        rec["events"] = ev
    ev.append({"ts": _utc_now(), "message": message})
    if len(ev) > 50:
        del ev[:-50]

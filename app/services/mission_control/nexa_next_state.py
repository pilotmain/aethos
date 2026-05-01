"""
Aggregated Mission Control **runtime state** for dynamic UI (Nexa Next).

Maps existing orchestration assignments into a stable ``missions`` / ``tasks`` shape until
dedicated ``missions`` / ``mission_tasks`` tables exist.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.nexa_next_runtime import NexaArtifact, NexaExternalCall, NexaMission, NexaMissionTask
from app.services.events.bus import list_events
from app.services.metrics.runtime import snapshot as metrics_process_snapshot
from app.services.mission_control.read_model import build_mission_control_summary

# Ephemeral streams (privacy audit / provider gateway) until those are persisted.
_PRIVACY_EVENTS_CAP = 400
STATE: dict[str, Any] = {
    "privacy_events": [],
    "provider_events": [],
    "last_updated": None,
}


def add_privacy_event(event: dict[str, Any]) -> None:
    STATE["privacy_events"].append(event)
    while len(STATE["privacy_events"]) > _PRIVACY_EVENTS_CAP:
        STATE["privacy_events"].pop(0)


def add_provider_event(event: dict[str, Any]) -> None:
    STATE["provider_events"].append(event)
    while len(STATE["provider_events"]) > _PRIVACY_EVENTS_CAP:
        STATE["provider_events"].pop(0)


def derive_privacy_indicator(privacy_events: list[Any]) -> dict[str, Any]:
    """
    Worst recent signal wins for UI badge (Phase 13).

    Returns stable keys: ``level`` ∈ {safe, redacted, blocked}.
    """
    recent = list(privacy_events)[-120:] if privacy_events else []
    blocked = False
    redacted = False
    for ev in reversed(recent):
        if not isinstance(ev, dict):
            continue
        t = str(ev.get("type") or "")
        if t in ("secret_blocked", "pii_blocked_by_policy"):
            blocked = True
            break
        if t == "pii_redacted":
            redacted = True
    if blocked:
        return {"level": "blocked", "label": "Blocked", "severity": 3}
    if redacted:
        return {"level": "redacted", "label": "Redacted", "severity": 2}
    return {"level": "safe", "label": "Safe (no PII)", "severity": 1}


def summarize_provider_transparency(
    provider_events: list[Any],
    *,
    privacy_events: list[Any],
) -> dict[str, Any]:
    """Roll-ups for Mission Control transparency panel."""
    by_prov: dict[str, dict[str, int]] = {}
    for e in provider_events:
        if not isinstance(e, dict):
            continue
        p = str(e.get("provider") or "unknown")
        st = str(e.get("status") or "")
        slot = by_prov.setdefault(p, {"calls": 0, "blocked": 0, "fallback": 0, "completed": 0})
        slot["calls"] += 1
        if st in ("blocked", "rate_limited", "external_calls_disabled", "strict_privacy_mode"):
            slot["blocked"] += 1
        elif st == "fallback":
            slot["fallback"] += 1
        elif st == "completed":
            slot["completed"] += 1

    redactions = sum(
        1
        for ev in privacy_events
        if isinstance(ev, dict) and str(ev.get("type") or "") == "pii_redacted"
    )
    blocks = sum(
        1
        for ev in privacy_events
        if isinstance(ev, dict)
        and str(ev.get("type") or "") in ("secret_blocked", "pii_blocked_by_policy")
    )

    tail = [e for e in provider_events if isinstance(e, dict)][-16:]
    return {
        "by_provider": by_prov,
        "privacy_redactions_observed": redactions,
        "privacy_blocks_observed": blocks,
        "recent_provider_events": tail,
    }


def _runtime_hints() -> dict[str, Any]:
    s = get_settings()
    has_remote = bool((s.openai_api_key or "").strip() or (s.anthropic_api_key or "").strip())
    offline_mode = not has_remote and not s.nexa_disable_external_calls
    return {
        "offline_mode": offline_mode,
        "strict_privacy_mode": bool(s.nexa_strict_privacy_mode),
        "remote_providers_available": has_remote,
        "external_calls_disabled": bool(s.nexa_disable_external_calls),
    }


def _agent_performance_from_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, Any]] = {}
    for t in tasks:
        h = str(t.get("agent_handle") or "").strip()
        if not h:
            continue
        slot = agg.setdefault(
            h,
            {"tasks_completed": 0, "tasks_failed": 0, "latency_sum_ms": 0.0, "latency_n": 0},
        )
        st = str(t.get("status") or "").lower()
        if st == "completed":
            slot["tasks_completed"] += 1
        elif st in ("failed", "cancelled"):
            slot["tasks_failed"] += 1
        dm = t.get("duration_ms")
        if isinstance(dm, (int, float)) and dm >= 0:
            slot["latency_sum_ms"] += float(dm)
            slot["latency_n"] += 1

    out: list[dict[str, Any]] = []
    for handle in sorted(agg.keys()):
        a = agg[handle]
        n = int(a["latency_n"])
        out.append(
            {
                "agent_handle": handle,
                "tasks_completed": int(a["tasks_completed"]),
                "tasks_failed": int(a["tasks_failed"]),
                "avg_latency_ms": round(a["latency_sum_ms"] / n, 2) if n else None,
            }
        )
    return out


def _mission_reliability_metrics(
    db: Session,
    *,
    user_id: str | None,
    missions_out: list[dict[str, Any]],
    tasks_out: list[dict[str, Any]],
) -> dict[str, Any]:
    total_m = len(missions_out)
    completed_m = sum(1 for m in missions_out if str(m.get("status") or "") == "completed")
    success_rate = (completed_m / total_m) if total_m else 1.0

    durs = [
        float(t["duration_ms"])
        for t in tasks_out
        if isinstance(t.get("duration_ms"), (int, float)) and float(t["duration_ms"]) >= 0
    ]
    avg_runtime_ms = sum(durs) / len(durs) if durs else 0.0

    q = select(func.count()).select_from(NexaExternalCall).where(NexaExternalCall.blocked.is_(True))
    if user_id:
        q = q.where(NexaExternalCall.user_id == user_id)
    blocked_calls = int(db.scalar(q) or 0)

    snap = metrics_process_snapshot()
    return {
        "success_rate": round(success_rate, 4),
        "avg_runtime_ms": round(avg_runtime_ms, 2),
        "blocked_calls": blocked_calls,
        "missions_completed": completed_m,
        "missions_total": total_m,
        "process": {
            "provider_calls_total": snap["provider_calls_total"],
            "privacy_blocks_total": snap["privacy_blocks_total"],
            "provider_latency_avg_ms": snap["provider_latency_avg_ms"],
            "missions_completed_total": snap["missions_completed_total"],
            "missions_timeout_total": snap["missions_timeout_total"],
        },
    }


def update_state(result: list[dict[str, Any]]) -> None:
    _ = result
    STATE["last_updated"] = datetime.now(timezone.utc).isoformat()


def build_execution_snapshot(db: Session, *, user_id: str | None = None) -> dict[str, Any]:
    """Mission Control execution view: DB-backed missions/tasks/artifacts + bus + ephemeral streams."""
    q = select(NexaMission).order_by(NexaMission.created_at.desc())
    if user_id:
        q = q.where(NexaMission.user_id == user_id)
    mission_rows = list(db.scalars(q).all())

    missions_out = []
    for m in mission_rows:
        it = getattr(m, "input_text", None)
        if it and len(it) > 5000:
            it = it[:5000] + "…"
        missions_out.append(
            {
                "id": m.id,
                "user_id": m.user_id,
                "title": m.title,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "input_text": it,
            }
        )

    mids = [m.id for m in mission_rows]
    tasks_out: list[dict[str, Any]] = []
    artifacts_out: list[dict[str, Any]] = []
    if mids:
        task_rows = db.scalars(select(NexaMissionTask).where(NexaMissionTask.mission_id.in_(mids))).all()
        tasks_out = [
            {
                "id": t.id,
                "mission_id": t.mission_id,
                "agent_handle": t.agent_handle,
                "role": t.role,
                "task": t.task,
                "status": t.status,
                "depends_on": t.depends_on or [],
                "output": t.output_json,
                "started_at": t.started_at.isoformat() if getattr(t, "started_at", None) else None,
                "duration_ms": getattr(t, "duration_ms", None),
            }
            for t in task_rows
        ]
        art_rows = db.scalars(select(NexaArtifact).where(NexaArtifact.mission_id.in_(mids))).all()
        artifacts_out = [
            {
                "id": a.id,
                "mission_id": a.mission_id,
                "agent": a.agent_handle,
                "artifact": a.artifact_json,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in art_rows
        ]

    priv = list(STATE["privacy_events"])
    prov = list(STATE["provider_events"])

    return {
        "missions": missions_out,
        "tasks": tasks_out,
        "artifacts": artifacts_out,
        "events": list_events(),
        "privacy_events": priv,
        "provider_events": prov,
        "last_updated": STATE.get("last_updated"),
        "privacy_indicator": derive_privacy_indicator(priv),
        "provider_transparency": summarize_provider_transparency(prov, privacy_events=priv),
        "runtime": _runtime_hints(),
        "metrics": _mission_reliability_metrics(
            db,
            user_id=user_id,
            missions_out=missions_out,
            tasks_out=tasks_out,
        ),
        "agent_performance": _agent_performance_from_tasks(tasks_out),
    }


def build_mission_control_runtime_state(db: Session, user_id: str, *, hours: int = 24) -> dict[str, Any]:
    """Shape expected by ``GET /mission-control/state`` — live-backed, no static mocks."""
    summary = build_mission_control_summary(db, user_id, hours=hours)
    orch = summary.get("orchestration") or {}
    assigns: list[dict[str, Any]] = list(orch.get("assignments") or [])

    missions_by_spawn: dict[str, list[dict[str, Any]]] = defaultdict(list)
    loose: list[dict[str, Any]] = []
    for a in assigns:
        ij = a.get("input_json") if isinstance(a.get("input_json"), dict) else {}
        sg = str(ij.get("spawn_group_id") or "").strip()
        row = {
            "assignment_id": a.get("id"),
            "agent_handle": a.get("assigned_to_handle"),
            "title": a.get("title"),
            "status": a.get("status"),
            "spawn_group_id": sg or None,
        }
        if sg:
            missions_by_spawn[sg].append(row)
        else:
            loose.append(row)

    missions_out = [
        {"spawn_group_id": sg, "tasks": rows, "kind": "spawn_group"}
        for sg, rows in sorted(missions_by_spawn.items(), key=lambda x: x[0])
    ]
    if loose:
        missions_out.append({"spawn_group_id": None, "tasks": loose, "kind": "ungrouped"})

    agents = [
        {
            "handle": a.get("assigned_to_handle"),
            "assignment_id": a.get("id"),
            "status": a.get("status"),
        }
        for a in assigns
    ]

    tasks = [
        {
            "id": a.get("id"),
            "title": a.get("title"),
            "status": a.get("status"),
            "agent_handle": a.get("assigned_to_handle"),
            "spawn_group_id": (a.get("input_json") or {}).get("spawn_group_id")
            if isinstance(a.get("input_json"), dict)
            else None,
        }
        for a in assigns
    ]

    return {
        "missions": missions_out,
        "agents": agents,
        "tasks": tasks,
        "events": [],
        "artifacts": [],
        "privacy_events": [],
        "hours": summary.get("hours"),
        "generated_at": summary.get("overview") is not None,
        "legacy_summary_window": {"hours": hours},
    }

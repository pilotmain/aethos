"""Mission Control execution snapshot builders — DB-backed missions/tasks plus live event streams."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.dev_runtime import NexaDevRun, NexaDevWorkspace
from app.models.nexa_next_runtime import NexaArtifact, NexaExternalCall, NexaMission, NexaMissionTask
from app.services.events.bus import list_events
from app.services.metrics.runtime import snapshot as metrics_process_snapshot

MC_MAX_MISSIONS_LOADED = 50
MC_MAX_ARTIFACTS_PER_MISSION = 100

# Ephemeral streams (privacy audit / provider gateway) until those are persisted.
_PRIVACY_EVENTS_CAP = 400
STATE: dict[str, Any] = {
    "privacy_events": [],
    "provider_events": [],
    "integrity_alerts": [],
    "integrity_alert_ignored_ids": {},
    "privacy_override_log": [],
    "last_updated": None,
}

_INTEGRITY_ALERTS_CAP = 80
_PRIVACY_OVERRIDE_LOG_CAP = 200


def compute_privacy_score(
    *,
    privacy_events: list[Any],
    integrity_alerts: list[Any],
    overrides_count: int,
) -> int:
    """Heuristic 0–100 score: higher is healthier privacy posture for this session snapshot."""
    score = 100
    red = sum(
        1 for e in privacy_events if isinstance(e, dict) and str(e.get("type") or "") == "pii_redacted"
    )
    blk = sum(
        1
        for e in privacy_events
        if isinstance(e, dict)
        and str(e.get("type") or "") in ("secret_blocked", "pii_blocked_by_policy")
    )
    score -= min(25, blk * 5)
    score -= min(20, red * 2)
    crit = sum(
        1 for a in integrity_alerts if isinstance(a, dict) and str(a.get("severity") or "").lower() == "critical"
    )
    warn = sum(
        1 for a in integrity_alerts if isinstance(a, dict) and str(a.get("severity") or "").lower() == "warning"
    )
    score -= min(25, crit * 8)
    score -= min(15, warn * 3)
    score += min(15, max(0, overrides_count) * 3)
    return max(0, min(100, int(score)))


def add_integrity_alert(entry: dict[str, Any]) -> None:
    """Ephemeral UI/runtime alerts for Phase 17 integrity violations (non-secret signals)."""
    STATE.setdefault("integrity_alerts", []).append(entry)
    while len(STATE["integrity_alerts"]) > _INTEGRITY_ALERTS_CAP:
        STATE["integrity_alerts"].pop(0)


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
        if st in (
            "blocked",
            "rate_limited",
            "external_calls_disabled",
            "strict_privacy_mode",
            "user_privacy_paranoid",
            "paranoid_pii_in_output",
        ):
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


def _ignored_alert_ids_map() -> dict[str, Any]:
    STATE.setdefault("integrity_alert_ignored_ids", {})
    return STATE["integrity_alert_ignored_ids"]


def _scope_ephemeral(events: list[Any], uid: str | None) -> list[Any]:
    """Phase 20 — Mission Control streams isolated per authenticated user."""
    if uid is None:
        return list(events)
    return [e for e in events if isinstance(e, dict) and e.get("user_id") == uid]


def _scope_override_log(uid: str | None) -> list[Any]:
    raw = list(STATE.get("privacy_override_log") or [])[-24:]
    if uid is None:
        return raw
    return [e for e in raw if isinstance(e, dict) and e.get("user_id") == uid]


def _override_count_for_user(uid: str | None) -> int:
    m = _ignored_alert_ids_map()
    if not uid:
        return len(m)
    return sum(1 for v in m.values() if isinstance(v, dict) and v.get("user_id") == uid)


def _integrity_banner_level(alerts: list[Any], ignored_ids: frozenset[str] | None = None) -> str | None:
    """Worst unresolved severity for Mission Control banner (Phase 18)."""
    ig = ignored_ids or frozenset()
    critical = False
    warning = False
    for a in alerts:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("alert_id") or "")
        if aid and aid in ig:
            continue
        sev = a.get("severity")
        if sev is None:
            t = str(a.get("type") or "").lower()
            if "pii" in t:
                warning = True
            else:
                critical = True
            continue
        sl = str(sev).lower()
        if sl == "critical":
            critical = True
        elif sl == "warning":
            warning = True
    if critical:
        return "critical"
    if warning:
        return "warning"
    return None


def _annotate_integrity_alerts(alerts: list[Any]) -> list[dict[str, Any]]:
    ignored = _ignored_alert_ids_map()
    out: list[dict[str, Any]] = []
    for a in alerts:
        if not isinstance(a, dict):
            continue
        row = dict(a)
        aid = str(row.get("alert_id") or "")
        row["ignored"] = bool(aid and aid in ignored)
        out.append(row)
    return out


def apply_integrity_alert_override(
    alert_id: str,
    action: str,
    *,
    user_id: str,
) -> dict[str, Any]:
    """
    User-controlled dismissal for **warning** integrity alerts only (Phase 19).

    Critical / secret-related alerts cannot be overridden.
    """
    from app.services.privacy_firewall.audit import log_event

    if action != "ignore":
        raise ValueError("unsupported action")
    aid = str(alert_id or "").strip()
    if not aid:
        raise KeyError("alert_id required")

    alerts = STATE.get("integrity_alerts") or []
    hit = next((a for a in alerts if isinstance(a, dict) and str(a.get("alert_id")) == aid), None)
    if not hit:
        raise KeyError("unknown alert")

    owner = hit.get("user_id")
    if owner is not None and owner != user_id:
        raise PermissionError("alert belongs to another user")

    sev = str(hit.get("severity") or "").lower()
    if sev == "critical":
        raise PermissionError("cannot override critical alerts")
    typ = str(hit.get("type") or "").lower()
    if "secret" in typ:
        raise PermissionError("cannot override secret alerts")

    ignored = _ignored_alert_ids_map()
    now = datetime.now(timezone.utc).isoformat()
    ignored[aid] = {"user_id": user_id, "action": action, "at": now}

    entry = {
        "type": "privacy_alert_override",
        "alert_id": aid,
        "action": action,
        "user_id": user_id,
        "at": now,
        "final_outcome": "ignored",
        "explanation_snapshot": hit.get("explanation"),
        "source_alert_type": hit.get("type"),
    }
    STATE.setdefault("privacy_override_log", []).append(entry)
    while len(STATE["privacy_override_log"]) > _PRIVACY_OVERRIDE_LOG_CAP:
        STATE["privacy_override_log"].pop(0)

    log_event(entry)
    return {"ok": True, "alert_id": aid, "action": action, "outcome": "ignored"}


def _runtime_hints(
    *,
    db: Session | None = None,
    scoped_user_id: str | None = None,
    privacy_events_scoped: list[Any] | None = None,
    integrity_alerts_scoped: list[Any] | None = None,
) -> dict[str, Any]:
    from app.services.user_settings.service import effective_privacy_mode

    s = get_settings()
    has_remote = bool((s.openai_api_key or "").strip() or (s.anthropic_api_key or "").strip())
    offline_mode = not has_remote and not s.nexa_disable_external_calls
    priv = privacy_events_scoped if privacy_events_scoped is not None else list(STATE.get("privacy_events") or [])
    alerts = integrity_alerts_scoped if integrity_alerts_scoped is not None else list(STATE.get("integrity_alerts") or [])
    ignored_map = _ignored_alert_ids_map()
    ignored_ids = frozenset(ignored_map.keys())
    active_banner = bool(alerts) and any(
        isinstance(a, dict) and str(a.get("alert_id") or "") not in ignored_ids for a in alerts
    )
    score = compute_privacy_score(
        privacy_events=list(priv),
        integrity_alerts=list(alerts),
        overrides_count=_override_count_for_user(scoped_user_id),
    )
    mode_label = effective_privacy_mode(db, scoped_user_id)
    return {
        "offline_mode": offline_mode,
        "strict_privacy_mode": bool(s.nexa_strict_privacy_mode),
        "remote_providers_available": has_remote,
        "external_calls_disabled": bool(s.nexa_disable_external_calls),
        "integrity_alert_active": active_banner,
        "integrity_banner_level": _integrity_banner_level(alerts, ignored_ids),
        "user_privacy_mode": mode_label,
        "privacy_score": score,
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


def build_execution_snapshot(
    db: Session,
    *,
    user_id: str | None = None,
    hours: int = 24,
) -> dict[str, Any]:
    """Mission Control unified view: execution snapshot plus orchestration/trust dashboard (when ``user_id`` set)."""
    q = select(NexaMission).order_by(NexaMission.created_at.desc())
    if user_id:
        q = q.where(NexaMission.user_id == user_id)
    q = q.limit(MC_MAX_MISSIONS_LOADED)
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
        art_rows = list(
            db.scalars(
                select(NexaArtifact)
                .where(NexaArtifact.mission_id.in_(mids))
                .order_by(NexaArtifact.created_at.desc())
            ).all()
        )
        by_mid: dict[str, list[Any]] = defaultdict(list)
        for a in art_rows:
            by_mid[a.mission_id].append(a)
        artifacts_out = []
        for mid in mids:
            for a in by_mid.get(mid, [])[:MC_MAX_ARTIFACTS_PER_MISSION]:
                artifacts_out.append(
                    {
                        "id": a.id,
                        "mission_id": a.mission_id,
                        "agent": a.agent_handle,
                        "artifact": a.artifact_json,
                        "created_at": a.created_at.isoformat() if a.created_at else None,
                    }
                )

    priv = _scope_ephemeral(list(STATE["privacy_events"]), user_id)
    prov = _scope_ephemeral(list(STATE["provider_events"]), user_id)
    alerts_scoped = _scope_ephemeral(list(STATE.get("integrity_alerts") or []), user_id)
    alert_tail = alerts_scoped[-40:]
    rh = _runtime_hints(
        db=db,
        scoped_user_id=user_id,
        privacy_events_scoped=priv,
        integrity_alerts_scoped=alerts_scoped,
    )

    dev_workspaces_out: list[dict[str, Any]] = []
    dev_runs_out: list[dict[str, Any]] = []
    if user_id:
        ws_rows = list(
            db.scalars(
                select(NexaDevWorkspace)
                .where(NexaDevWorkspace.user_id == user_id)
                .order_by(NexaDevWorkspace.created_at.desc())
                .limit(40)
            ).all()
        )
        dev_workspaces_out = [
            {
                "id": w.id,
                "name": w.name,
                "repo_path": w.repo_path,
                "status": w.status,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in ws_rows
        ]
        dr_rows = list(
            db.scalars(
                select(NexaDevRun)
                .where(NexaDevRun.user_id == user_id)
                .order_by(NexaDevRun.created_at.desc())
                .limit(40)
            ).all()
        )
        dev_runs_out = [
            {
                "id": r.id,
                "workspace_id": r.workspace_id,
                "goal": r.goal[:500] + ("…" if len(r.goal or "") > 500 else ""),
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "error": r.error,
                "adapter_used": (r.result_json or {}).get("adapter_used")
                if isinstance(r.result_json, dict)
                else None,
                "preferred_agent": (r.result_json or {}).get("preferred_agent")
                if isinstance(r.result_json, dict)
                else None,
                "iterations": (r.result_json or {}).get("iterations")
                if isinstance(r.result_json, dict)
                else None,
                "tests_passed": (r.result_json or {}).get("tests_passed")
                if isinstance(r.result_json, dict)
                else None,
                "pr_ready": (r.result_json or {}).get("pr_ready")
                if isinstance(r.result_json, dict)
                else None,
                "max_iterations": (r.result_json or {}).get("max_iterations")
                if isinstance(r.result_json, dict)
                else None,
                "has_runtime_errors": (r.result_json or {}).get("has_runtime_errors")
                if isinstance(r.result_json, dict)
                else None,
                "privacy_note": "Outbound adapter context is gated; stored output is redacted.",
                "privacy_warnings": None,
            }
            for r in dr_rows
        ]

    exec_payload: dict[str, Any] = {
        "missions": missions_out,
        "tasks": tasks_out,
        "artifacts": artifacts_out,
        "events": list_events(),
        "privacy_events": priv,
        "provider_events": prov,
        "integrity_alerts": _annotate_integrity_alerts(alert_tail),
        "last_updated": STATE.get("last_updated"),
        "privacy_indicator": derive_privacy_indicator(priv),
        "provider_transparency": summarize_provider_transparency(prov, privacy_events=priv),
        "privacy_audit": {
            "recent_overrides": _scope_override_log(user_id),
            "privacy_score": rh.get("privacy_score"),
        },
        "runtime": rh,
        "metrics": _mission_reliability_metrics(
            db,
            user_id=user_id,
            missions_out=missions_out,
            tasks_out=tasks_out,
        ),
        "agent_performance": _agent_performance_from_tasks(tasks_out),
        "dev_workspaces": dev_workspaces_out,
        "dev_runs": dev_runs_out,
    }

    uid = (user_id or "").strip()
    if uid:
        from app.services.mission_control.read_model import build_mission_control_dashboard

        dash = build_mission_control_dashboard(db, uid, hours=hours)
        return {**exec_payload, **dash}

    return exec_payload

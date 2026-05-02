"""Phase 45A — drain pending autonomous tasks through :class:`~app.services.gateway.runtime.NexaGateway`."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.autonomy import NexaAutonomousTask
from app.services.autonomy.efficiency import compress_context
from app.services.autonomy.feedback import record_task_feedback
from app.services.autonomy.intelligence import build_intelligent_context
from app.services.autonomy.safety import should_execute
from app.services.events.unified_event import emit_unified_event
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.memory.memory_index import MemoryIndex
from app.services.tasks.unified_task import NexaTask


def get_pending_tasks(db: Session, user_id: str, *, limit: int) -> list[NexaAutonomousTask]:
    uid = (user_id or "").strip()
    if not uid:
        return []
    return list(
        db.scalars(
            select(NexaAutonomousTask)
            .where(NexaAutonomousTask.user_id == uid, NexaAutonomousTask.state == "pending")
            .order_by(desc(NexaAutonomousTask.priority), NexaAutonomousTask.created_at)
            .limit(int(limit))
        ).all()
    )


def _merge_context_execution(ctx_json: str, patch: dict[str, Any]) -> str:
    try:
        base = json.loads(ctx_json or "{}")
    except json.JSONDecodeError:
        base = {}
    ex = dict(base.get("execution") or {})
    ex.update(patch)
    base["execution"] = ex
    return json.dumps(base, ensure_ascii=False)[:50_000]


def build_autonomy_gateway_context(row: NexaAutonomousTask) -> GatewayContext:
    """Map a DB row to a gateway context with compressed memory intel."""
    uid = row.user_id
    try:
        blob = json.loads(row.context_json or "{}")
    except json.JSONDecodeError:
        blob = {}
    nt = blob.get("nexa_task") or {}
    task = NexaTask(
        id=row.id,
        type=str(nt.get("type") or "system"),
        input=(row.title or "").strip(),
        context=dict(nt.get("context") or {}),
        priority=int(row.priority or 0),
        auto_generated=bool(row.auto_generated),
        origin=str(row.origin or "autonomy"),
    )
    intel = build_intelligent_context(task, user_id=uid, max_chars=2200, memory_fn=MemoryIndex())
    intel = compress_context(intel)
    mem = {
        "memory_context": (intel.get("prompt_injection") or "")[:3500],
        "autonomy_intel": intel,
    }
    return GatewayContext(
        user_id=uid,
        channel="autonomy",
        memory=mem,
        extras={
            "via_gateway": True,
            "autonomous_task_id": row.id,
            "autonomy_phase": 45,
        },
    )


def execute_autonomous_tasks(
    db: Session,
    user_id: str,
    *,
    max_tasks: int | None = None,
) -> dict[str, Any]:
    """
    Run up to ``max_tasks`` pending autonomous tasks for one user through the gateway.
    """
    s = get_settings()
    cap = int(max_tasks if max_tasks is not None else getattr(s, "nexa_autonomy_max_tasks_per_cycle", 5) or 5)
    cap = max(1, min(cap, 8))
    if not getattr(s, "nexa_autonomous_mode", False) or not getattr(s, "nexa_autonomy_execution_enabled", True):
        return {"ok": False, "skipped": True, "reason": "autonomy_execution_off", "results": []}

    rows = get_pending_tasks(db, user_id, limit=cap)
    gw = NexaGateway()
    results: list[dict[str, Any]] = []
    for row in rows:
        allow, reason = should_execute(db, user_id, task_row=row)
        if not allow:
            results.append({"id": row.id, "skipped": reason})
            continue

        now = datetime.now(timezone.utc)
        row.state = "running"
        row.updated_at = now
        db.commit()
        text = (row.title or "").strip()[:50_000]
        gctx = build_autonomy_gateway_context(row)
        try:
            out = gw.handle_message(gctx, text, db=db)
            success = _outcome_success(out)
            reply = str(out.get("text") or "")[:2000] if isinstance(out, dict) else ""
            cost = _estimate_cost_usd(out)
            row.state = "completed" if success else "failed"
            row.context_json = _merge_context_execution(
                row.context_json,
                {
                    "at": now.isoformat(),
                    "success": success,
                    "reply_preview": reply[:500],
                    "cost_usd": cost,
                    "mode": out.get("mode") if isinstance(out, dict) else None,
                },
            )
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
            try:
                from app.services.autonomy.intelligence import update_memory_weights

                entry_ids = []
                if isinstance(gctx.memory, dict):
                    intel = gctx.memory.get("autonomy_intel") or {}
                    entry_ids = list(intel.get("selected_entry_ids") or [])
                update_memory_weights(
                    user_id,
                    {
                        "success": success,
                        "entry_ids": entry_ids,
                    },
                )
            except Exception:
                pass
            record_task_feedback(
                db,
                user_id=user_id,
                task_id=row.id,
                outcome="success" if success else "fail",
                reason="autonomy_gateway",
                meta={
                    "success": success,
                    "iterations": 1,
                    "cost": cost,
                    "mode": out.get("mode") if isinstance(out, dict) else None,
                },
            )
            emit_unified_event(
                "autonomy.task.executed",
                task_id=row.id,
                user_id=user_id,
                payload={"success": success, "cost_usd": cost},
            )
            results.append({"id": row.id, "success": success, "cost_usd": cost})
        except Exception as exc:
            row.state = "failed"
            row.context_json = _merge_context_execution(
                row.context_json,
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "success": False,
                    "error": str(exc)[:2000],
                },
            )
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
            record_task_feedback(
                db,
                user_id=user_id,
                task_id=row.id,
                outcome="fail",
                reason="autonomy_exception",
                meta={"success": False, "iterations": 0, "cost": 0.0, "error": str(exc)[:500]},
            )
            results.append({"id": row.id, "error": str(exc)[:200]})
    return {"ok": True, "user_id": user_id, "results": results}


def _outcome_success(out: dict[str, Any]) -> bool:
    if not isinstance(out, dict):
        return False
    if out.get("ok") is False:
        return False
    if out.get("mode") == "chat" and (out.get("text") or "").strip():
        return True
    return out.get("dev_run", {}).get("ok") is True if isinstance(out.get("dev_run"), dict) else False


def _estimate_cost_usd(out: dict[str, Any]) -> float:
    dr = out.get("dev_run")
    if isinstance(dr, dict) and dr.get("cost_usd") is not None:
        try:
            return float(dr["cost_usd"])
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def run_autonomy_executor_for_all_pending_users(db: Session) -> dict[str, Any]:
    """
    Heartbeat helper: one pass per distinct user with pending work (bounded).
    """
    s = get_settings()
    if not getattr(s, "nexa_autonomous_mode", False) or not getattr(s, "nexa_autonomy_execution_enabled", True):
        return {"ok": False, "skipped": True}

    uids = list(
        db.scalars(
            select(NexaAutonomousTask.user_id)
            .where(NexaAutonomousTask.state == "pending")
            .distinct()
            .limit(int(getattr(s, "nexa_autonomy_max_users_per_heartbeat", 12) or 12))
        ).all()
    )
    merged: list[dict[str, Any]] = []
    for uid in uids:
        u = (uid or "").strip()
        if not u:
            continue
        merged.append(execute_autonomous_tasks(db, u))
    return {"ok": True, "users": len(merged), "runs": merged}


__all__ = [
    "build_autonomy_gateway_context",
    "execute_autonomous_tasks",
    "get_pending_tasks",
    "run_autonomy_executor_for_all_pending_users",
]

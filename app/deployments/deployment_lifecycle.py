# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Stage transitions, checkpoint history, and structured deployment logs."""

from __future__ import annotations

import uuid
from typing import Any

from app.deployments.deployment_registry import get_deployment, upsert_deployment
from app.deployments.deployment_stages import is_known_stage, is_terminal_stage, transition_allowed
from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import utc_now_iso


def _history(row: dict[str, Any]) -> list[dict[str, Any]]:
    h = row.setdefault("stage_history", [])
    if not isinstance(h, list):
        row["stage_history"] = []
        return row["stage_history"]
    return h


def _checkpoints(row: dict[str, Any]) -> list[dict[str, Any]]:
    c = row.setdefault("checkpoints", [])
    if not isinstance(c, list):
        row["checkpoints"] = []
        return row["checkpoints"]
    return c


def _infer_stage_from_legacy(row: dict[str, Any]) -> str:
    ds = str(row.get("deployment_stage") or "").strip()
    if ds and is_known_stage(ds):
        return ds
    s = str(row.get("status") or "").strip()
    if s in ("completed", "failed", "rolled_back", "cancelled", "recovering"):
        return "recovering" if s == "recovering" else s
    cp = row.get("checkpoint") if isinstance(row.get("checkpoint"), dict) else {}
    cs = str(cp.get("stage") or "").strip()
    if cs in ("completed", "failed", "rolled_back"):
        return cs
    if cs == "deploy_step":
        return "deploying"
    return "created"


def record_checkpoint(
    st: dict[str, Any],
    deployment_id: str,
    *,
    stage: str,
    message: str = "",
    data: dict[str, Any] | None = None,
    artifacts: list[Any] | None = None,
) -> dict[str, Any]:
    row = get_deployment(st, deployment_id)
    if not row:
        return {}
    ts = utc_now_iso()
    cp = {
        "checkpoint_id": f"cp_{uuid.uuid4().hex[:12]}",
        "deployment_id": str(deployment_id),
        "stage": str(stage)[:64],
        "created_at": ts,
        "data": dict(data or {}),
        "artifacts": list(artifacts or []),
        "logs": [{"ts": ts, "message": (message or "")[:2000]}],
    }
    _checkpoints(row).append(cp)
    if len(_checkpoints(row)) > 120:
        del _checkpoints(row)[:-120]
    upsert_deployment(st, deployment_id, {"checkpoints": _checkpoints(row)})
    orchestration_log.log_deployments_event(
        "deployment_checkpoint_created",
        deployment_id=str(deployment_id),
        checkpoint_id=cp["checkpoint_id"],
        stage=str(stage),
    )
    emit_runtime_event(
        st,
        "deployment_checkpoint_created",
        deployment_id=str(deployment_id),
        checkpoint_id=cp["checkpoint_id"],
        stage=str(stage),
    )
    return cp


def transition_deployment_stage(
    st: dict[str, Any],
    deployment_id: str,
    to_stage: str,
    *,
    reason: str = "",
    sync_status: bool = True,
) -> dict[str, Any] | None:
    """Advance ``deployment_stage`` with history + logs (keeps ``status`` aligned when ``sync_status``)."""
    row = get_deployment(st, deployment_id)
    if not row:
        return None
    cur = _infer_stage_from_legacy(row)
    tgt = str(to_stage).strip()
    if cur == tgt:
        return row
    if not transition_allowed(cur, tgt):
        orchestration_log.log_deployments_event(
            "deployment_stage_rejected",
            deployment_id=str(deployment_id),
            from_stage=cur,
            to_stage=tgt,
            reason=(reason or "transition_not_allowed")[:500],
        )
        return row
    ts = utc_now_iso()
    hist = _history(row)
    hist.append({"ts": ts, "from": cur, "to": tgt, "reason": (reason or "")[:2000]})
    if len(hist) > 200:
        del hist[:-200]
    patch: dict[str, Any] = {
        "deployment_stage": tgt,
        "stage_history": hist,
        "updated_at": ts,
    }
    if sync_status:
        if is_terminal_stage(tgt):
            if tgt == "rolled_back":
                patch["status"] = "rolled_back"
            elif tgt == "completed":
                patch["status"] = "completed"
            elif tgt in ("failed", "cancelled"):
                patch["status"] = tgt
        elif tgt == "recovering":
            patch["status"] = "recovering"
        else:
            patch["status"] = "running"
    upsert_deployment(st, deployment_id, patch)
    orchestration_log.log_deployments_event(
        "deployment_stage_changed",
        deployment_id=str(deployment_id),
        from_stage=cur,
        to_stage=tgt,
    )
    emit_runtime_event(
        st,
        "deployment_stage_changed",
        deployment_id=str(deployment_id),
        from_stage=cur,
        to_stage=tgt,
        user_id=str(row.get("user_id") or ""),
        environment_id=str(row.get("environment_id") or ""),
    )
    logs = list(row.get("logs") or [])
    if isinstance(logs, list):
        logs.append({"ts": ts, "message": f"stage:{cur}->{tgt}", "detail": (reason or "")[:1500]})
        upsert_deployment(st, deployment_id, {"logs": logs[-500:]})
    record_checkpoint(st, deployment_id, stage=tgt, message=f"stage {tgt}", data={"from": cur})
    return get_deployment(st, deployment_id)


def bootstrap_new_deployment(
    st: dict[str, Any],
    deployment_id: str,
    *,
    environment_id: str,
    user_id: str,
    task_id: str,
    plan_id: str,
) -> None:
    """Apply the deterministic happy-path prefix up to ``queued`` (rest driven by execution)."""
    ts = utc_now_iso()
    upsert_deployment(
        st,
        deployment_id,
        {
            "deployment_stage": "created",
            "stage_history": [{"ts": ts, "from": "", "to": "created", "reason": "bootstrap"}],
            "checkpoints": [],
        },
    )
    for s in ("preflight", "queued", "building"):
        transition_deployment_stage(st, deployment_id, s, reason="bootstrap", sync_status=True)

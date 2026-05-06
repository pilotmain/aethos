"""background_heartbeat tool — durable status without invisible work."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.agent_team import AgentAssignment
from app.services.agent_runtime.defaults import default_memory_json
from app.services.agent_runtime.paths import heartbeats_json_path, memory_dir, memory_json_path
from app.services.agent_runtime.tool_registry import is_tool_enabled
from app.services.agent_runtime.validation import validate_background_heartbeat
from app.services.agent_runtime.workspace_files import (
    append_timeline_event,
    atomic_write_json,
    ensure_seed_files,
    read_json_file,
)
from app.services.audit_service import audit
from app.services.custom_agents import normalize_agent_key

_RATE_PATH_REL = "heartbeat_rate.json"
_MIN_INTERVAL_SEC = 1.0


def _rate_state_path() -> Path:
    ensure_seed_files()
    return memory_dir() / _RATE_PATH_REL


def _rate_limit_ok(user_id: str, agent: str, assignment_id: int | None) -> bool:
    key = f"{user_id}:{agent}:{assignment_id if assignment_id is not None else 'none'}"
    p = _rate_state_path()
    data = read_json_file(p, {})
    now = time.time()
    last = float(data.get(key) or 0.0)
    if now - last < _MIN_INTERVAL_SEC:
        return False
    data[key] = now
    atomic_write_json(p, data)
    return True


def background_heartbeat(db: Session, *, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    if not get_settings().nexa_agent_tools_enabled:
        raise RuntimeError("NEXA_AGENT_TOOLS_ENABLED is false")
    if not is_tool_enabled("background_heartbeat"):
        raise RuntimeError("background_heartbeat is not enabled in agent_tools.json")

    err = validate_background_heartbeat(payload)
    if err:
        raise ValueError(err)

    handle = normalize_agent_key(str(payload.get("agent_handle") or ""))
    aid_raw = payload.get("assignment_id")
    aid: int | None = int(aid_raw) if aid_raw is not None else None

    if not _rate_limit_ok(uid, handle, aid):
        raise ValueError("heartbeat rate limited; wait before sending another")

    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if aid is not None:
        row = db.get(AgentAssignment, aid)
        if row is None or row.user_id != uid:
            raise ValueError("assignment_id not found for this user")
        st = str(payload.get("status") or "")
        allowed_status = {
            "queued",
            "running",
            "waiting_approval",
            "waiting_worker",
            "blocked",
            "completed",
            "failed",
            "cancelled",
            "assigned",
        }
        if st in allowed_status:
            row.status = st
        hb_blob = dict(row.output_json or {}) if isinstance(row.output_json, dict) else {}
        hb_blob["last_heartbeat"] = {
            "message": str(payload.get("message") or "")[:2000],
            "progress_percent": payload.get("progress_percent"),
            "recorded_at": now_iso,
            "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        }
        row.output_json = hb_blob
        db.add(row)
        db.commit()
        db.refresh(row)

    hb_path = heartbeats_json_path()
    hb_data = read_json_file(hb_path, {"version": "1.0", "heartbeats": {}})
    hb_bucket = hb_data.setdefault("heartbeats", {})
    hk = f"{handle}:{aid if aid is not None else 'none'}:{payload.get('spawn_group_id') or 'none'}"
    hb_bucket[hk] = {
        "agent_handle": handle,
        "assignment_id": aid,
        "spawn_group_id": payload.get("spawn_group_id"),
        "status": str(payload.get("status") or ""),
        "message": str(payload.get("message") or "")[:2000],
        "progress_percent": payload.get("progress_percent"),
        "next_check_at": payload.get("next_check_at"),
        "recorded_at": now_iso,
    }
    hb_data["last_updated_at"] = now_iso
    atomic_write_json(hb_path, hb_data)

    mem_path = memory_json_path()
    mem = read_json_file(mem_path, default_memory_json())
    mem["last_updated_at"] = now_iso
    atomic_write_json(mem_path, mem)

    sg = payload.get("spawn_group_id")
    append_timeline_event(
        {
            "event": "heartbeat",
            "user_id": uid,
            "agent_handle": handle,
            "assignment_id": aid,
            "spawn_group_id": sg if sg else None,
            "status": str(payload.get("status") or ""),
            "message": str(payload.get("message") or "")[:500],
            "at": now_iso,
        }
    )

    audit(
        db,
        event_type="agent_session.heartbeat",
        actor="aethos",
        user_id=uid,
        message=f"Heartbeat @{handle} assignment={aid}",
        metadata={
            "agent_handle": handle,
            "assignment_id": aid,
            "status": str(payload.get("status") or ""),
        },
        job_id=None,
    )

    return {"ok": True, "recorded_at": now_iso}

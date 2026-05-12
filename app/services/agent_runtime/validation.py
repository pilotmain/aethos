# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight payload validation (no jsonschema dependency)."""

from __future__ import annotations

import re
from typing import Any

_HANDLE = re.compile(r"^[a-zA-Z0-9_-]{2,64}$")


def validate_sessions_spawn(payload: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        return "payload must be an object"
    req = ("requested_by", "sessions", "goal", "timebox_minutes", "approval_policy")
    for k in req:
        if k not in payload:
            return f"missing field: {k}"
    rb = str(payload.get("requested_by") or "").strip()
    if len(rb) < 1 or len(rb) > 128:
        return "requested_by invalid"
    goal = str(payload.get("goal") or "").strip()
    if len(goal) < 5 or len(goal) > 2000:
        return "goal length must be 5–2000"
    sessions = payload.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        return "sessions must be a non-empty array"
    if len(sessions) > 10:
        return "max 10 sessions"
    tb = payload.get("timebox_minutes")
    try:
        tb_int = int(tb)
    except (TypeError, ValueError):
        return "timebox_minutes must be an integer"
    if tb_int < 1 or tb_int > 480:
        return "timebox_minutes must be 1–480"
    pol = payload.get("approval_policy")
    if not isinstance(pol, dict) or not str(pol.get("mode") or "").strip():
        return "approval_policy.mode required"
    mode = str(pol.get("mode"))
    allowed_modes = (
        "plan_only",
        "approval_required_for_tools",
        "workspace_grant_required",
        "deny_external_side_effects",
    )
    if mode not in allowed_modes:
        return f"invalid approval_policy.mode: {mode}"
    for i, s in enumerate(sessions):
        if not isinstance(s, dict):
            return f"sessions[{i}] must be object"
        for fk in ("agent_handle", "role", "task"):
            if fk not in s:
                return f"sessions[{i}] missing {fk}"
        h = str(s.get("agent_handle") or "").strip()
        if not _HANDLE.match(h):
            return f"invalid agent_handle in sessions[{i}]"
        task = str(s.get("task") or "").strip()
        if len(task) < 5 or len(task) > 2000:
            return f"sessions[{i}] task length must be 5–2000"
    return None


def validate_background_heartbeat(payload: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        return "payload must be an object"
    for k in ("agent_handle", "status", "message"):
        if k not in payload:
            return f"missing field: {k}"
    h = str(payload.get("agent_handle") or "").strip()
    if not _HANDLE.match(h):
        return "invalid agent_handle"
    st = str(payload.get("status") or "")
    allowed = (
        "queued",
        "running",
        "waiting_approval",
        "waiting_worker",
        "blocked",
        "completed",
        "failed",
        "cancelled",
        "assigned",
    )
    if st not in allowed:
        return "invalid status"
    msg = str(payload.get("message") or "")
    if len(msg) < 1 or len(msg) > 2000:
        return "message length must be 1–2000"
    aid = payload.get("assignment_id")
    if aid is not None:
        try:
            int(aid)
        except (TypeError, ValueError):
            return "assignment_id must be integer or null"
    return None

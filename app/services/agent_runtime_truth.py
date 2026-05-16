# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Orchestrator visibility into runtime workers — answers from truth, not LLM fallback (Phase 3 Step 6)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.runtime.agent_work_state import (
    find_runtime_agent_by_handle,
    find_runtime_agent_by_registry_id,
    get_output,
    handle_at,
    list_tasks_for_agent,
    normalize_handle,
)
from app.services.agent.activity_tracker import get_activity_tracker
from app.services.gateway.context import GatewayContext
from app.services.sub_agent_registry import AgentRegistry, AgentStatus
from app.services.sub_agent_router import orchestration_chat_key, resolve_agent_for_dispatch

_RE_RESULT_QUERY = re.compile(
    r"(?is)(?:what\s+(?:is|are)\s+(?:the\s+)?)?(?:result|results|output|outputs|status)\s+"
    r"(?:of\s+)?(?:@)?([a-zA-Z0-9_-]+)(?:\s+work|\s+job|\s+task)?\s*\??\s*$"
)
_RE_DOING_QUERY = re.compile(
    r"(?is)(?:what\s+(?:is|are)\s+)?(?:@)?([a-zA-Z0-9_-]+)\s+(?:doing|working\s+on)\s*\??\s*$"
)
_RE_DID_QUERY = re.compile(
    r"(?is)(?:what\s+did\s+)?(?:@)?([a-zA-Z0-9_-]+)\s+(?:do|complete|finish)\s*\??\s*$"
)
_RE_SHOW_RESULT = re.compile(
    r"(?is)^(?:show|get)\s+(?:@)?([a-zA-Z0-9_-]+)(?:\s+)?(?:result|results|output|status)\s*\??\s*$"
)
_RE_LIST_AGENTS = re.compile(
    r"(?is)^(?:list|show)\s+(?:my\s+)?(?:orchestration\s+)?agents?\s*\??\s*$"
)


def extract_agent_query_handle(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    for rx in (_RE_RESULT_QUERY, _RE_DOING_QUERY, _RE_DID_QUERY, _RE_SHOW_RESULT):
        m = rx.match(t)
        if m:
            return m.group(1)
    m = re.search(r"@([a-zA-Z0-9_-]+)", t)
    if m and any(k in t.lower() for k in ("result", "output", "status", "doing", "completed", "work")):
        return m.group(1)
    return None


def _resolve_agent(
    handle: str,
    *,
    chat_id: str,
    user_id: str | None,
) -> tuple[Any | None, dict[str, Any] | None]:
    registry = AgentRegistry()
    sub = resolve_agent_for_dispatch(registry, handle, chat_id, user_id)
    runtime = find_runtime_agent_by_handle(handle)
    if sub is None and runtime is None:
        alt = normalize_handle(handle)
        sub = resolve_agent_for_dispatch(registry, alt, chat_id, user_id)
        runtime = find_runtime_agent_by_handle(alt)
    if runtime is None and sub is not None:
        runtime = find_runtime_agent_by_registry_id(sub.id)
    return sub, runtime


def format_agent_status_reply(
    handle: str,
    *,
    sub: Any | None = None,
    runtime: dict[str, Any] | None = None,
    chat_id: str | None = None,
    user_id: str | None = None,
) -> str:
    h = handle_at(handle)
    if runtime is None:
        runtime = find_runtime_agent_by_handle(handle)
    if sub is None and chat_id:
        sub, _ = _resolve_agent(handle, chat_id=chat_id, user_id=user_id)
    if sub is None and runtime is None:
        return (
            f"{h} was not found in this workspace.\n\n"
            "Create one with `create a … agent` or `/subagent create <name> <domain>`."
        )

    reg_id = str((sub.id if sub else None) or (runtime or {}).get("registry_agent_id") or "")
    aid = str((runtime or {}).get("agent_id") or reg_id)
    status = str((runtime or {}).get("status") or (sub.status.value if sub else "unknown"))
    if sub and sub.status == AgentStatus.TERMINATED:
        return _format_expired_agent_reply(h, runtime, sub)

    tasks = list_tasks_for_agent(aid) if aid else []
    current = (runtime or {}).get("current_task_id")
    if not tasks and not current:
        tracker = get_activity_tracker()
        recent = tracker.get_agent_history(reg_id, limit=3) if reg_id else []
        if recent:
            last = recent[0]
            preview = (last.get("output") or last.get("input") or "")[:400]
            return (
                f"{h} exists ({status}).\n\n"
                f"No tracked task in runtime truth right now. Latest action: **{last.get('action_type')}**.\n"
                f"{preview}"
            )
        domain = (sub.domain if sub else None) or (runtime or {}).get("role") or "general"
        return (
            f"{h} exists and is **{status}** ({domain}).\n\n"
            "No task has been assigned yet. Ask it to work with:\n"
            f"`{h} <your request>`"
        )

    task = tasks[0]
    tstate = str(task.get("state") or task.get("status") or "queued")
    prompt = str(task.get("prompt") or "")[:300]
    if tstate in ("queued", "scheduled"):
        return (
            f"{h} has a queued task:\n**{prompt or '(no prompt)'}**\n\nNo output yet."
        )
    if tstate in ("running", "busy", "retrying"):
        return (
            f"{h} is working on:\n**{prompt or '(task)'}**\n\n"
            f"Current status: **{tstate}**."
        )
    if tstate == "failed":
        out_id = task.get("latest_output_id")
        out = get_output(str(out_id)) if out_id else None
        reason = (out or {}).get("summary") or task.get("result_summary") or "Task failed."
        return (
            f"{h} failed while working on:\n**{prompt}**\n\n"
            f"Reason: {reason}\n\n"
            "Next: retry, inspect logs, or reassign."
        )
    out_id = task.get("latest_output_id") or (runtime or {}).get("latest_output_id")
    out = get_output(str(out_id)) if out_id else None
    if out:
        body = (out.get("content") or out.get("summary") or "")[:2000]
        arts = out.get("artifacts") or []
        art_line = f"\n\nArtifacts: {', '.join(arts)}" if arts else ""
        return f"{h} completed:\n**{prompt}**\n\nResult:\n{body}{art_line}"
    return f"{h} completed:\n**{prompt}**\n\n(No stored output body — check Mission Control runtime workers.)"


def _format_expired_agent_reply(h: str, runtime: dict[str, Any] | None, sub: Any) -> str:
    aid = str((runtime or {}).get("agent_id") or "")
    tasks = list_tasks_for_agent(aid) if aid else []
    if tasks and tasks[0].get("state") == "completed":
        return format_agent_status_reply(
            h.lstrip("@"),
            sub=sub,
            runtime=runtime,
        ).replace("exists and is", "is no longer active; last task was")
    return f"{h} is no longer active. History remains in runtime truth and `/subagent show`."


def try_route_agent_status_query(
    user_input: str,
    chat_id: str,
    *,
    user_id: str | None = None,
    db: Session | None = None,
) -> dict[str, Any] | None:
    """Sub-agent router hook — status/result queries without execution."""
    _ = db
    t = (user_input or "").strip()
    if _RE_LIST_AGENTS.match(t):
        registry = AgentRegistry()
        agents = (
            registry.list_agents_for_app_user(user_id)
            if user_id
            else registry.list_agents(chat_id)
        )
        if not agents:
            return {
                "handled": True,
                "response": "No orchestration agents yet. Say `create a marketing agent` or `/subagent list`.",
            }
        lines = ["Orchestration agents (runtime-backed):", ""]
        for ag in agents[:24]:
            rt = find_runtime_agent_by_registry_id(ag.id)
            st = (rt or {}).get("status") or ag.status.value
            lines.append(f"• @{ag.name} ({ag.domain}) — {st}")
        return {"handled": True, "response": "\n".join(lines)}

    handle = extract_agent_query_handle(t)
    if not handle:
        return None
    sub, runtime = _resolve_agent(handle, chat_id=chat_id, user_id=user_id)
    return {
        "handled": True,
        "response": format_agent_status_reply(
            handle, sub=sub, runtime=runtime, chat_id=chat_id, user_id=user_id
        ),
        "agent_id": (sub.id if sub else None) or (runtime or {}).get("agent_id"),
        "agent_name": handle,
        "clean_message": "",
    }


def try_agent_runtime_truth_gateway_turn(
    gctx: GatewayContext,
    user_text: str,
    db: Session | None = None,
) -> dict[str, Any] | None:
    """Gateway hook — answer agent work questions from runtime truth before general_chat LLM."""
    from app.core.config import get_settings

    if not bool(getattr(get_settings(), "nexa_agent_orchestration_enabled", False)):
        return None
    chat_key = orchestration_chat_key(gctx)
    routed = try_route_agent_status_query(
        user_text,
        chat_key,
        user_id=(gctx.user_id or "").strip() or None,
        db=db,
    )
    if not routed or not routed.get("handled"):
        return None
    from app.services.gateway.runtime import gateway_finalize_chat_reply

    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(
            str(routed.get("response") or ""),
            source="agent_runtime_truth",
            user_text=user_text,
        ),
        "intent": "agent_status_query",
    }


def build_agent_visibility_for_truth() -> dict[str, Any]:
    """Slice for Mission Control / runtime truth."""
    from app.runtime.runtime_agents import list_runtime_agents

    workers: list[dict[str, Any]] = []
    for aid, row in list_runtime_agents(include_expired=True).items():
        if not isinstance(row, dict) or row.get("system"):
            continue
        tasks = list_tasks_for_agent(str(aid), limit=3)
        workers.append(
            {
                "agent_id": aid,
                "handle": row.get("handle"),
                "display_name": row.get("display_name"),
                "role": row.get("role"),
                "status": row.get("status"),
                "registry_agent_id": row.get("registry_agent_id"),
                "current_task_id": row.get("current_task_id"),
                "latest_output_id": row.get("latest_output_id"),
                "tasks": tasks,
                "created_by": row.get("created_by"),
            }
        )
    return {"workers": workers, "count": len(workers)}

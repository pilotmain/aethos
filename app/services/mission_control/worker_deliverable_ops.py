# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Worker detail, deliverable export, follow-up priority, and privacy (Phase 3 Step 8)."""

from __future__ import annotations

import json
import re
from typing import Any

from app.runtime.agent_work_state import find_runtime_agent_by_handle, list_tasks_for_agent, normalize_handle
from app.runtime.worker_operational_memory import (
    build_worker_memory,
    get_deliverable,
    get_session_active_worker,
    list_deliverables_for_worker,
    list_continuations_for_worker,
    search_deliverables,
)
from app.services.mission_control.runtime_worker_visibility import build_runtime_workers_view
from app.services.worker_intelligence import build_worker_operational_summary

_RE_MENTION = re.compile(r"@([a-zA-Z0-9_-]+)")
_RE_EXPORT = re.compile(r"(?is)^export\s+(?:that|the\s+report|the\s+summary|it)\s*\??\s*$")
_RE_SUMMARIZE = re.compile(r"(?is)^summarize\s+(?:the\s+)?(?:research|report|last\s+result)\s*\??\s*$")
_RE_EXPAND = re.compile(r"(?is)^(?:expand|show\s+me\s+more)(?:\s+(?:the\s+)?last\s+result)?\s*\??\s*$")
_RE_COMPARE = re.compile(r"(?is)^compare\s+(?:it\s+)?with\s+(?:the\s+)?previous\s*\??\s*$")
_RE_WHAT_DID = re.compile(
    r"(?is)(?:what\s+did\s+(?:the\s+)?)?@?([\w-]+)\s+(?:do|produce|find|complete)\s*\??\s*$"
)
_RE_FAILED_REPAIR = re.compile(r"(?is)failed\s+repair\s+reports?")


def build_worker_detail(worker_id: str, *, user_id: str | None = None) -> dict[str, Any]:
    from app.runtime.runtime_agents import list_runtime_agents

    row = (list_runtime_agents(include_expired=True)).get(worker_id)
    if not isinstance(row, dict) or row.get("system"):
        return {"found": False, "worker_id": worker_id}
    mem = build_worker_memory(worker_id)
    dels = list_deliverables_for_worker(worker_id, limit=12)
    conts = list_continuations_for_worker(worker_id, limit=8)
    summ = build_worker_operational_summary(worker_id, row)
    tasks = list_tasks_for_agent(worker_id, limit=8)
    from app.services.mission_control.runtime_ownership import build_ownership_chains

    chains = [c for c in build_ownership_chains(user_id) if c.get("runtime_agent_id") == worker_id]
    return {
        "found": True,
        "worker_id": worker_id,
        "status": row.get("status"),
        "role": row.get("role"),
        "handle": row.get("handle"),
        "display_name": row.get("display_name"),
        "current_task_id": row.get("current_task_id"),
        "recent_tasks": tasks,
        "latest_output_id": row.get("latest_output_id"),
        "deliverables": [_public_deliverable(d) for d in dels],
        "artifacts": row.get("latest_artifact_ids") or [],
        "memory_summary": mem.get("memory_summary"),
        "memory": mem,
        "continuations": conts,
        "success_rate": summ.get("success_rate"),
        "provider": row.get("provider"),
        "model": row.get("model"),
        "workspace_context": (mem.get("workspace_context") or [])[-3:],
        "ownership_chain": chains[:6],
    }


def build_deliverable_detail(deliverable_id: str) -> dict[str, Any]:
    row = get_deliverable(deliverable_id)
    if not row:
        return {"found": False, "deliverable_id": deliverable_id}
    return {"found": True, "deliverable": _public_deliverable(row)}


def export_deliverable(deliverable_id: str, *, fmt: str = "markdown") -> dict[str, Any]:
    row = get_deliverable(deliverable_id)
    if not row:
        return {"ok": False, "error": "not_found"}
    fmt_l = (fmt or "markdown").strip().lower()
    pub = _public_deliverable(row)
    if fmt_l == "json":
        body = json.dumps(pub, indent=2, default=str)
        content_type = "application/json"
    elif fmt_l == "text":
        body = _text_export(pub)
        content_type = "text/plain"
    else:
        body = _markdown_export(pub)
        content_type = "text/markdown"
    return {
        "ok": True,
        "deliverable_id": deliverable_id,
        "format": fmt_l,
        "content_type": content_type,
        "body": body,
    }


def resolve_followup_priority(
    text: str,
    *,
    chat_key: str,
    handle: str | None = None,
) -> tuple[str | None, str]:
    """Returns (reply, resolution_source)."""
    from app.services.worker_intelligence import resolve_worker_followup

    base = resolve_worker_followup(text, chat_key=chat_key, handle=handle)
    if base:
        return base, "worker_intelligence"

    t = (text or "").strip()
    if not t:
        return None, "none"

    explicit = _RE_MENTION.search(t)
    if explicit:
        h = explicit.group(1)
        rt = find_runtime_agent_by_handle(h)
        if rt:
            return format_worker_result_reply(str(rt.get("agent_id")), h), "explicit_mention"

    worker_id = get_session_active_worker(chat_key)
    if worker_id:
        if _RE_EXPORT.match(t):
            dels = list_deliverables_for_worker(worker_id, limit=1)
            if dels:
                ex = export_deliverable(str(dels[0].get("deliverable_id")), fmt="markdown")
                if ex.get("ok"):
                    return f"Export ready ({ex.get('format')}):\n\n{ex.get('body', '')[:3000]}", "session_export"
        if _RE_EXPAND.match(t) or _RE_SUMMARIZE.match(t):
            return format_worker_result_reply(worker_id), "session_latest"
        if _RE_COMPARE.match(t) and worker_id:
            dels = list_deliverables_for_worker(worker_id, limit=2)
            if len(dels) >= 2:
                a, b = dels[0], dels[1]
                return (
                    f"**Latest:** {a.get('summary')}\n\n**Previous:** {b.get('summary')}",
                    "session_compare",
                )

    m = _RE_WHAT_DID.match(t)
    if m:
        return format_worker_result_reply_by_handle(m.group(1), chat_key=chat_key), "what_did_agent"

    if _RE_FAILED_REPAIR.search(t):
        rows = search_deliverables(deliverable_type="repair_summary", status="failed", limit=6)
        if not rows:
            rows = [r for r in search_deliverables(deliverable_type="repair_summary", limit=6) if r.get("status") == "failed"]
        if rows:
            lines = ["**Failed repair reports:**", ""]
            for r in rows:
                lines.append(f"• {r.get('summary', '')[:120]}")
            return "\n".join(lines), "search_failed_repair"

    return None, "none"


def format_worker_result_reply(worker_id: str, handle_hint: str | None = None) -> str:
    from app.runtime.runtime_agents import list_runtime_agents

    row = (list_runtime_agents(include_expired=True)).get(worker_id)
    if not isinstance(row, dict):
        return f"Worker `{worker_id}` not found."
    h = handle_hint or str(row.get("handle") or worker_id)
    tasks = list_tasks_for_agent(worker_id, limit=1)
    task_prompt = (tasks[0].get("prompt") if tasks else None) or "—"
    status = str(row.get("status") or "unknown")
    dels = list_deliverables_for_worker(worker_id, limit=3)
    lines = [
        f"{h} — **{status}**",
        "",
        f"**Task:** {task_prompt[:200]}",
        "",
        "**Summary:**",
    ]
    if dels:
        lines.append(dels[0].get("summary") or "—")
        lines.append("")
        lines.append("**Deliverables:**")
        for d in dels[:3]:
            lines.append(f"• {d.get('title') or d.get('type')} — {d.get('summary', '')[:100]}")
        arts = dels[0].get("artifacts") or []
        if arts:
            lines.append("")
            lines.append(f"**Artifacts:** {', '.join(str(a) for a in arts[:6])}")
    else:
        lines.append("No deliverables yet.")
    lines.append("")
    lines.append("**Next:** expand the analysis, export the report, or assign a follow-up task.")
    return "\n".join(lines)


def format_worker_result_reply_by_handle(handle: str, *, chat_key: str | None = None) -> str:
    rt = find_runtime_agent_by_handle(handle)
    if rt:
        return format_worker_result_reply(str(rt["agent_id"]), handle)
    return f"@{normalize_handle(handle)} was not found."


def apply_deliverable_privacy(row: dict[str, Any]) -> dict[str, Any]:
    """Redact deliverable content when policy requires; attach privacy metadata."""
    from app.core.config import get_settings
    from app.privacy.pii_detection import detect_pii
    from app.privacy.pii_redaction import redact_text
    from app.privacy.privacy_policy import current_privacy_mode
    from app.privacy.redaction_policy import should_redact_for_external_model

    out = dict(row)
    s = get_settings()
    mode = current_privacy_mode(s)
    blob = f"{out.get('summary', '')} {out.get('content', '')}"
    cats = detect_pii(blob)
    redacted = False
    if cats and should_redact_for_external_model(s):
        out["content"] = redact_text(str(out.get("content") or ""))
        out["summary"] = redact_text(str(out.get("summary") or ""))
        redacted = True
    out["privacy_metadata"] = {
        "mode": str(mode.value if hasattr(mode, "value") else mode),
        "pii_categories": cats,
        "redacted": redacted,
    }
    return out


def deliverable_trace_link(deliverable_id: str, worker_id: str, task_id: str) -> dict[str, Any]:
    return {
        "deliverable_id": deliverable_id,
        "worker_id": worker_id,
        "task_id": task_id,
        "chain": ["orchestrator", "runtime_worker", "task", "deliverable"],
    }


def _public_deliverable(row: dict[str, Any]) -> dict[str, Any]:
    pub = apply_deliverable_privacy(dict(row))
    wid = str(pub.get("worker_id") or "")
    from app.runtime.runtime_agents import list_runtime_agents

    wrow = (list_runtime_agents(include_expired=True)).get(wid) or {}
    pub["worker_handle"] = wrow.get("handle")
    pub.setdefault("title", pub.get("summary", "")[:80] or pub.get("type"))
    return pub


def _markdown_export(pub: dict[str, Any]) -> str:
    return (
        f"# {pub.get('title', 'Deliverable')}\n\n"
        f"**Type:** {pub.get('type')}  \n"
        f"**Worker:** {pub.get('worker_handle')}  \n"
        f"**Task:** {pub.get('task_id')}  \n"
        f"**Created:** {pub.get('created_at')}  \n"
        f"**Status:** {pub.get('status')}  \n\n"
        f"## Summary\n\n{pub.get('summary', '')}\n\n"
        f"## Content\n\n{pub.get('content', '')}\n"
    )


def _text_export(pub: dict[str, Any]) -> str:
    return (
        f"{pub.get('title')}\n"
        f"{pub.get('summary', '')}\n\n"
        f"{pub.get('content', '')}\n"
    )

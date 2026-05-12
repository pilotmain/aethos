# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic Web chat replies for host job status (no LLM)."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.services.agent_job_service import AgentJobService

# Import at end of function to avoid import cycle with web_chat_service

_STATUS_PAT = re.compile(
    r"(?is)^\s*(any\s+)?update\s*\.?\s*$"
    r"|^\s*status\s*\.?\s*$"
    r"|^\s*job\s+status\s*\.?\s*$"
    r"|^\s*what(?:'s| is)\s+the\s+status\s*\.?\s*$"
    r"|^\s*check\s+(?:on\s+)?(?:the\s+)?job\s*\.?\s*$"
    r"|^\s*any\s+news\s*\.?\s*$"
    r"|^\s*report\s+progress(?:\s+please)?\s*\.?\s*$"
    r"|^\s*(?:any\s+)?progress\s+please\s*\.?\s*$"
    r"|^\s*still\s+running\s*\.?\s*$"
    r"|^\s*what\s+happened\s*\.?\s*$"
    r"|^\s*are\s+you\s+done\s*\??\s*$"
)

_TERMINAL = frozenset({"completed", "failed", "cancelled", "rejected", "blocked", "error"})


def is_web_host_status_query(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 240:
        return False
    return bool(_STATUS_PAT.match(t))


def _format_assignment_activity_block(app_user_id: str, db: Session) -> str:
    from app.services.agent_team.service import summarize_assignment_progress

    prog = summarize_assignment_progress(db, user_id=app_user_id)
    if not prog:
        return ""
    lines = []
    for a in prog[:15]:
        hlab = str(a.get("assigned_to_handle_display") or a.get("assigned_to_handle") or "")
        lines.append(
            f"#{a['id']} `@{hlab}` — **{a['status']}** — {str(a.get('title') or '')[:120]}"
        )
    return "**Team activity**\n\n" + "\n".join(lines)


def try_web_host_job_status_reply(
    db: Session,
    app_user_id: str,
    user_text: str,
    *,
    web_session_id: str,
):
    """If the user asks for status/update, prefer assignment activity then session host jobs."""
    from app.services.web_chat_service import WebChatResult

    if not is_web_host_status_query(user_text):
        return None

    wid = (web_session_id or "default").strip()[:64] or "default"

    assignment_block = _format_assignment_activity_block(app_user_id, db)

    svc = AgentJobService()
    jobs = svc.list_jobs(db, app_user_id, limit=80)
    matched: list = []
    for j in jobs:
        if (j.worker_type or "") != "local_tool":
            continue
        if (j.command_type or "").lower() != "host-executor":
            continue
        pl = dict(j.payload_json or {})
        co = pl.get("chat_origin") if isinstance(pl.get("chat_origin"), dict) else {}
        if (co.get("web_session_id") or "") != wid:
            continue
        matched.append(j)

    base_dec = {
        "agent": "aethos",
        "action": "host_job_status",
        "tool": "host_executor",
        "reason": "Deterministic status for this Web chat session (no LLM).",
        "risk": "low",
        "approval_required": False,
        "intent": "host_job_status",
    }
    team_dec = {
        "agent": "aethos",
        "action": "assignment_activity",
        "tool": "agent_team",
        "reason": "Recent assignments for this account (no LLM).",
        "risk": "low",
        "approval_required": False,
        "intent": "team_progress",
    }

    if not matched:
        if assignment_block:
            return WebChatResult(
                reply=assignment_block,
                intent="team_progress",
                agent_key="aethos",
                response_kind="team_progress",
                related_job_ids=[],
                decision_summary=team_dec,
            )
        return WebChatResult(
            reply=(
                "No active jobs are linked to this chat session. "
                "If you expected one, start a tracked job or assignment first."
            ),
            intent="host_job_status",
            agent_key="aethos",
            response_kind="host_job_status",
            related_job_ids=[],
        )

    matched.sort(key=lambda x: x.id, reverse=True)
    j = matched[0]
    st = (j.status or "").lower()
    title = (j.title or "Host action").strip()

    if st in _TERMINAL:
        if st == "completed":
            body = (j.result or "").strip() or "(no output)"
            host_reply = f"**{title}** · job #{j.id} · **completed**\n\n{body}"
        else:
            err = (j.error_message or "").strip() or st
            host_reply = f"**{title}** · job #{j.id} · **{j.status}**\n\n{err}"
    else:
        host_reply = (
            f"**{title}** · job #{j.id} · status **{j.status or 'running'}**. "
            "Use the Job tab for live updates, or wait — it will finish shortly."
        )

    if assignment_block:
        return WebChatResult(
            reply=f"{assignment_block}\n\n---\n\n{host_reply}",
            intent="mixed_progress",
            agent_key="aethos",
            response_kind="mixed_progress",
            related_job_ids=[j.id],
            decision_summary=base_dec,
        )

    return WebChatResult(
        reply=host_reply,
        intent="host_job_status",
        agent_key="aethos",
        response_kind="host_job_status",
        related_job_ids=[j.id],
        decision_summary=base_dec,
    )

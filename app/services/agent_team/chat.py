"""Conversational routing for agent organization (runs before host executor)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.services.agent_team.host_bridge import precheck_assignment_host_user_message
from app.services.agent_team.planner import (
    assignment_skips_host_path_inference,
    build_assignment_input_json,
    classify_assignment_instruction_kind,
    parse_explicit_assign,
    plan_tasks_from_goal,
)
from app.services.agent_team.service import (
    DuplicateAssignmentError,
    cancel_assignment,
    create_assignment,
    dispatch_assignment,
    get_assignment_status,
    get_or_create_default_organization,
    summarize_assignment_progress,
)
from app.services.custom_agents import (
    display_agent_handle,
    display_agent_handle_label,
    normalize_agent_key,
)
from app.services.mention_control import parse_mention

_RE_STATUS = re.compile(r"(?is)^\s*status\s+of\s+assignment\s+(\d+)\s*\.?\s*$")
_RE_CANCEL = re.compile(r"(?is)^\s*cancel\s+assignment\s+(\d+)\s*\.?\s*$")
_RE_CREATE_TEAM = re.compile(r"(?is)^\s*create\s+(?:an?\s+)?agent\s+team\b")
_RE_CREATE_TEAM_FOR_GOAL = re.compile(
    r"(?is)^\s*create\s+(?:an?\s+)?(?:(?:multi-agent|multi\s+agent)\s+)?(?:dev\s+)?(?:agent\s+)?team\s+for\s+(.+)$"
)
_RE_ASK_TEAM = re.compile(r"(?is)^\s*ask\s+my\s+team\s+to\s+(.+)$")
_RE_TEAM_STATUS = re.compile(
    r"(?is)^\s*(?:what\s+is\s+my\s+agent\s+team\s+working\s+on|what\s+is\s+my\s+team\s+working\s+on|what'?s\s+my\s+team\s+working\s+on)\??\s*$"
)
_RE_AGENT_WORKING = re.compile(
    r"(?is)^\s*what\s+is\s+@([a-z0-9][a-z0-9_-]*)\s+working\s+on\??\s*$"
)


def _assignment_handle_display(row: dict[str, Any]) -> str:
    return str(row.get("assigned_to_handle_display") or row.get("assigned_to_handle") or "").strip()


@dataclass(frozen=True)
class AgentTeamChatOutcome:
    """Deterministic agent-team reply + optional inline permission card payload for Web."""

    reply: str
    permission_required: dict[str, Any] | None = None
    assignment_ids: tuple[int, ...] = ()
    related_job_ids: tuple[int, ...] = ()


def _format_assignment_dispatch_reply(disp: dict[str, Any], row: Any, handle: str) -> str:
    aid = row.id
    hd = display_agent_handle_label(handle)
    if disp.get("waiting_approval"):
        msg = (disp.get("message") or "").strip()
        body = msg or "Approve the permission request in chat to continue."
        return (f"**Assignment #{aid}** `@{hd}` — **waiting_approval**\n\n{body}")[:12_000]
    if disp.get("host_job_id"):
        return (
            f"**Assignment #{aid}** `@{hd}` — **running** (host job **#{disp['host_job_id']}** queued)"
        )[:12_000]
    if not disp.get("ok"):
        err = disp.get("error") or "Assignment failed."
        return f"**Assignment #{aid}** `@{hd}` — **failed**\n\n{err}"[:12_000]
    out = disp.get("output")
    if isinstance(out, dict):
        txt = str(out.get("text") or "").strip()
        if txt:
            from app.services.markdown_postprocess import clean_agent_markdown_output

            txt = clean_agent_markdown_output(txt)
            return f"**Assignment #{aid}** `@{hd}`\n\n{txt}"[:12_000]
    return f"**Assignment #{aid}** `@{hd}`\n\n{(disp.get('error') or '(no output)')[:4000]}"


def _one_line_dispatch_summary(disp: dict[str, Any], row: Any, handle: str) -> str:
    hd = display_agent_handle_label(handle)
    if disp.get("waiting_approval"):
        return f"**#{row.id}** `@{hd}` — **waiting_approval**"
    if disp.get("host_job_id"):
        return f"**#{row.id}** `@{hd}` — host job **#{disp['host_job_id']}**"
    if not disp.get("ok"):
        return f"**#{row.id}** `@{hd}` — **failed**: {(disp.get('error') or '')[:400]}"
    out = disp.get("output")
    if isinstance(out, dict) and (out.get("text") or "").strip():
        return f"**#{row.id}** `@{hd}` → {(out.get('text') or '')[:400]}"
    return f"**#{row.id}** `@{hd}` → {(disp.get('error') or '(done)')[:400]}"


def agent_team_chat_blocks_folder_heuristics(text: str) -> bool:
    """When True, skip local folder/host inference for orchestration phrases."""
    raw = (text or "").strip()
    if not raw:
        return False
    low = raw.lower()
    if _RE_STATUS.match(raw) or _RE_CANCEL.match(raw):
        return True
    if _RE_CREATE_TEAM_FOR_GOAL.match(raw):
        return True
    if _RE_CREATE_TEAM.match(raw):
        return True
    if _RE_ASK_TEAM.match(raw):
        return True
    if _RE_TEAM_STATUS.match(raw):
        return True
    if _RE_AGENT_WORKING.match(raw):
        return True
    if low.startswith("assign @"):
        return True
    if low.startswith("@orchestrator") or low.startswith("@strategy"):
        return True
    if "agent team" in low and ("create" in low or "for" in low):
        return True
    return False


def try_agent_team_chat_turn(
    db: Session,
    app_user_id: str,
    user_text: str,
    *,
    web_session_id: str | None = None,
) -> AgentTeamChatOutcome | None:
    """
    Handle deterministic agent-team commands.

    Returns a structured outcome or None to continue the chat pipeline.
    """
    raw = (user_text or "").strip()
    if not raw:
        return None
    wid = (web_session_id or "").strip()[:64] or None

    team_line = raw
    mr_team = parse_mention(raw)
    if (
        mr_team.is_explicit
        and not mr_team.error
        and mr_team.agent_key == "strategy"
        and (mr_team.text or "").strip()
    ):
        team_line = (mr_team.text or "").strip()

    m = _RE_STATUS.match(team_line)
    if m:
        aid = int(m.group(1))
        st = get_assignment_status(db, assignment_id=aid, user_id=app_user_id)
        if not st:
            return AgentTeamChatOutcome(f"No assignment **#{aid}** for your account.")
        o = st.get("output_json") or {}
        err = st.get("error")
        out_txt = (o.get("text") or "").strip() if isinstance(o, dict) else ""
        hid = o.get("host_job_id") if isinstance(o, dict) else None
        body = err or out_txt or ("(host job queued)" if hid else "(no output yet)")
        rj: tuple[int, ...] = ()
        if hid is not None:
            try:
                rj = (int(hid),)
            except (TypeError, ValueError):
                rj = ()
        return AgentTeamChatOutcome(
            (
                f"**Assignment #{aid}** — `@{_assignment_handle_display(st)}` — **{st.get('status')}**\n\n{body[:8000]}"
            )[:12_000],
            assignment_ids=(aid,),
            related_job_ids=rj,
        )

    m = _RE_CANCEL.match(team_line)
    if m:
        aid = int(m.group(1))
        r = cancel_assignment(db, assignment_id=aid, user_id=app_user_id)
        if r.get("ok"):
            return AgentTeamChatOutcome(f"Cancelled assignment **#{aid}**.")
        return AgentTeamChatOutcome((r.get("error") or "Could not cancel.")[:2000])

    m_team_goal = _RE_CREATE_TEAM_FOR_GOAL.match(team_line)
    if m_team_goal:
        goal = (m_team_goal.group(1) or "").strip()[:4000]
        org = get_or_create_default_organization(db, app_user_id)
        gshort = goal[:500] + ("…" if len(goal) > 500 else "")
        return AgentTeamChatOutcome(
            (
                f"**Workspace** is ready (organization **#{org.id}** — {org.name}).\n\n"
                f"**Goal:** {gshort}\n\n"
                "You can coordinate with **@orchestrator**, assign concrete tasks with **assign @handle to …**, "
                "or say **ask my team to …** to queue tracked work.\n\n"
                "AethOS creates task-focused agents dynamically when the workload needs them."
            )
        )

    if _RE_CREATE_TEAM.match(team_line):
        org = get_or_create_default_organization(db, app_user_id)
        return AgentTeamChatOutcome(
            (
                f"Your **workspace** is ready (organization **#{org.id}** — {org.name}).\n\n"
                "Add agents via the API or say e.g. **assign @my-agent to …** to create work. "
                "Use **ask my team to …** to auto-route from keywords."
            )
        )

    m = _RE_ASK_TEAM.match(team_line)
    if m:
        goal = (m.group(1) or "").strip()
        org = get_or_create_default_organization(db, app_user_id)
        plans = plan_tasks_from_goal(goal)
        for p in plans:
            desc = str(p.get("description") or goal)[:4000]
            if assignment_skips_host_path_inference(desc):
                continue
            ok_pre, err_pre = precheck_assignment_host_user_message(
                db,
                user_id=app_user_id,
                user_message=desc,
                web_session_id=wid,
            )
            if not ok_pre:
                return AgentTeamChatOutcome(
                    f"**Cannot create assignments.**\n\n{err_pre or 'Invalid host path or request.'}"
                )
        lines: list[str] = []
        last_id: int | None = None
        assign_ids: list[int] = []
        job_ids: list[int] = []
        perm_echo: dict[str, Any] | None = None
        for p in plans:
            handle = normalize_agent_key(str(p.get("assigned_to") or ""))
            title = str(p.get("title") or "Task")[:500]
            desc = str(p.get("description") or goal)[:4000]
            ij = dict(p.get("input_json") or build_assignment_input_json(desc))
            ij.setdefault("user_message", desc)
            ij.setdefault("goal", goal[:4000])
            try:
                row = create_assignment(
                    db,
                    user_id=app_user_id,
                    assigned_to_handle=handle,
                    title=title,
                    description=desc,
                    organization_id=org.id,
                    assigned_by_handle="orchestrator",
                    input_json=ij,
                    web_session_id=wid,
                )
            except DuplicateAssignmentError as derr:
                ex = derr.existing
                hl = display_agent_handle_label(handle)
                return AgentTeamChatOutcome(
                    (
                        f"**Assignment not created** — similar work is already open: **#{ex.id}** "
                        f"`@{hl}` (**{ex.status}**). Say **status of assignment {ex.id}** or "
                        f"**cancel assignment {ex.id}** before queueing the same task again."
                    )[:12_000]
                )
            disp = dispatch_assignment(db, assignment_id=row.id, user_id=app_user_id)
            last_id = row.id
            assign_ids.append(row.id)
            if disp.get("permission_required") and perm_echo is None:
                perm_echo = disp["permission_required"]
            hj = disp.get("host_job_id")
            if hj is not None:
                try:
                    job_ids.append(int(hj))
                except (TypeError, ValueError):
                    pass
            lines.append(_one_line_dispatch_summary(disp, row, handle))
        if not lines:
            return None
        hdr = f"Processed **{len(lines)}** assignment(s). Latest id: **#{last_id}**.\n\n"
        return AgentTeamChatOutcome(
            hdr + "\n\n---\n\n".join(lines),
            permission_required=perm_echo,
            assignment_ids=tuple(assign_ids),
            related_job_ids=tuple(job_ids),
        )

    if _RE_TEAM_STATUS.match(team_line):
        prog = summarize_assignment_progress(db, user_id=app_user_id)
        if not prog:
            return AgentTeamChatOutcome(
                "No assignments yet. Try **ask my team to …** or **create a team** for a concrete goal."
            )
        lines = []
        ids: list[int] = []
        for a in prog[:15]:
            ids.append(int(a["id"]))
            lines.append(
                f"#{a['id']} `@{_assignment_handle_display(a)}` — **{a['status']}** — {a['title'][:120]}"
            )
        return AgentTeamChatOutcome(
            "**Team activity**\n\n" + "\n".join(lines),
            assignment_ids=tuple(ids),
        )

    m = _RE_AGENT_WORKING.match(team_line)
    if m:
        h = normalize_agent_key(m.group(1))
        rows = [
            a
            for a in summarize_assignment_progress(db, user_id=app_user_id)
            if normalize_agent_key(str(a.get("assigned_to_handle") or "")) == h
        ][:12]
        if not rows:
            return AgentTeamChatOutcome(f"No assignments for {display_agent_handle(h)} yet.")
        out_lines = [f"#{a['id']} — **{a['status']}** — {a['title'][:120]}" for a in rows]
        ids = tuple(int(a["id"]) for a in rows)
        return AgentTeamChatOutcome(
            f"**{display_agent_handle(h)}** — recent assignments\n\n"
            + "\n".join(out_lines),
            assignment_ids=ids,
        )

    parsed = parse_explicit_assign(team_line)
    if parsed:
        handle, instr = parsed
        if not instr:
            return AgentTeamChatOutcome(f"Add instructions after **assign @{handle} to …**.")
        kind = classify_assignment_instruction_kind(instr[:4000])
        input_body = build_assignment_input_json(instr[:4000], kind=kind)
        if kind == "file_folder" or not assignment_skips_host_path_inference(instr[:4000]):
            ok_pre, err_pre = precheck_assignment_host_user_message(
                db,
                user_id=app_user_id,
                user_message=instr[:4000],
                web_session_id=wid,
            )
            if not ok_pre:
                return AgentTeamChatOutcome(
                    f"**Assignment not created.**\n\n{err_pre or 'Invalid host path or request.'}"
                )
        org = get_or_create_default_organization(db, app_user_id)
        try:
            row = create_assignment(
                db,
                user_id=app_user_id,
                assigned_to_handle=handle,
                title=instr[:200],
                description=instr[:4000],
                organization_id=org.id,
                assigned_by_handle="user",
                input_json=input_body,
                web_session_id=wid,
            )
        except DuplicateAssignmentError as derr:
            ex = derr.existing
            hl = display_agent_handle_label(handle)
            return AgentTeamChatOutcome(
                (
                    f"**Assignment not created** — similar work is already open: **#{ex.id}** "
                    f"`@{hl}` (**{ex.status}**). Say **status of assignment {ex.id}** or "
                    f"**cancel assignment {ex.id}** before queueing the same task again."
                )[:12_000]
            )
        disp = dispatch_assignment(db, assignment_id=row.id, user_id=app_user_id)
        body = _format_assignment_dispatch_reply(disp, row, handle)
        rj: list[int] = []
        hj = disp.get("host_job_id")
        if hj is not None:
            try:
                rj.append(int(hj))
            except (TypeError, ValueError):
                pass
        return AgentTeamChatOutcome(
            body,
            permission_required=disp.get("permission_required"),
            assignment_ids=(row.id,),
            related_job_ids=tuple(rj),
        )

    return None

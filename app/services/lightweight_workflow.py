# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Lightweight multi-step flow: remember goal + step list in ConversationContext, chat only.
No auto-chains, no new UI, no background execution. User-driven; dev jobs still use normal approval.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.conversation_context import ConversationContext
from app.services.next_action_confirmation import (
    ack_line_for_injected_command,
    command_from_suggestion_line,
    is_injectable_command,
    risk_for_suggestion_command,
)

# Align with co-pilot suggestion TTL; flows feel stale after long silence
FLOW_TTL_SECONDS = 30 * 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_cmd(cmd: str) -> str:
    return re.sub(r"\s+", " ", (cmd or "").strip().lower())[:600]


def flow_step_exists_for_command(cctx: ConversationContext, command: str) -> bool:
    n = _norm_cmd(command)
    st0 = _load_flow(cctx.current_flow_state_json)
    if not st0:
        return False
    for s in st0.get("steps") or []:
        if _norm_cmd(str(s.get("command") or "")) == n:
            return True
    return False


@dataclass(frozen=True)
class FlowUserTurn:
    no_match: bool = True
    reprocess_user_text: str | None = None
    ack_line: str | None = None
    immediate_assistant: str | None = None
    clear_suggestions: bool = False
    # For freeform next-step, same "reply run" gate as co-pilot unknown lines
    store_pending_freeform: str | None = None


def _load_flow(raw: str | None) -> dict[str, Any] | None:
    if not (raw or "").strip():
        return None
    try:
        o = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(o, dict):
        return None
    return o


def _is_flow_expired(state: dict[str, Any], *, now: datetime) -> bool:
    u = str(state.get("updated_at") or state.get("created_at") or "")
    if not u:
        return True
    try:
        t = datetime.fromisoformat(u.replace("Z", "+00:00"))
    except ValueError:
        return True
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (now - t).total_seconds() > FLOW_TTL_SECONDS


def _step_type_from_command(cmd: str) -> str:
    c = (cmd or "").strip()
    m = re.match(r"^\s*@([A-Za-z][A-Za-z0-9_]*)", c) or re.match(
        r"^\s*/([A-Za-z][A-Za-z0-9_-]*)", c, re.IGNORECASE
    )
    if m:
        return m.group(1).lower()[:64]
    return "task"


def _goal_from_user_text(user_text: str) -> str | None:
    t = (user_text or "").strip()
    if not t or len(t) < 4:
        return None
    m = re.match(
        r"(?i)^\s*(help me|I want|I need|let's|we should|try to|need to)\s+(.+)$", t
    ) or re.match(
        r"(?i)^\s*(can you|could you|please|walk me through)\s+(.+?)(\.|$)\s*$", t
    )
    if m:
        g = (m.lastindex and m.group(m.lastindex) or t).strip()
        return (g or t)[:240] if (g or t) else None
    if 10 <= len(t) <= 240 and not t.startswith(("/", "@", "-")):
        return t[:240]
    return None


def _merge_or_create_flow_state(
    cctx: ConversationContext,
    user_text: str | None,
    shown_lines: list[str],
) -> None:
    clean = [str(x).strip() for x in shown_lines if str(x).strip()][:4]
    if not clean:
        return
    now = datetime.now(timezone.utc)
    ex = _load_flow(cctx.current_flow_state_json)
    if ex and _is_flow_expired(ex, now=now):
        ex = None
    if not ex:
        goal = _goal_from_user_text((user_text or "")) or (
            f"Next steps: {command_from_suggestion_line(clean[0])[:180]}"
        )
        st = {
            "goal": goal,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "steps": [],
            "last_action": None,
        }
    else:
        st = ex
        u = (user_text or "").strip()
        g2 = _goal_from_user_text(u) if u else None
        if g2 and len(g2) > 8 and not (st.get("goal") or "").strip():
            st["goal"] = g2
        st["updated_at"] = _now_iso()

    new_steps: list[dict[str, Any]] = []
    old = list(st.get("steps") or [])
    for i, line in enumerate(clean, start=1):
        cmd = command_from_suggestion_line(line)
        nc = _norm_cmd(cmd)
        status = "pending"
        for os in old:
            if _norm_cmd(str(os.get("command") or "")) == nc and str(
                os.get("status")
            ) == "done":
                status = "done"
                break
        new_steps.append(
            {
                "index": i,
                "type": _step_type_from_command(cmd),
                "status": status,
                "command": cmd[:1_200],
            }
        )
    st["steps"] = new_steps
    cctx.current_flow_state_json = json.dumps(st, ensure_ascii=False)


def merge_or_create_flow_state_from_suggestions(
    cctx: ConversationContext,
    user_text: str | None,
    shown_lines: list[str] | None,
) -> None:
    """Call when a Next steps block is shown. Safe no-op on empty list."""
    if not shown_lines:
        return
    _merge_or_create_flow_state(cctx, user_text, list(shown_lines or []))


def _pending_steps(st: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in (st.get("steps") or []) if str(s.get("status") or "") == "pending"]


def format_flow_bullet_summary(st: dict[str, Any], *, max_lines: int = 6) -> str:
    """Compact status for 'where are we' / continuity (no markdown bold — plain text in clients)."""
    gl = (st.get("goal") or "This workflow").strip()[:200]
    lines: list[str] = [f"Here’s where we are — {gl}:"]
    for i, s in enumerate((st.get("steps") or [])[:max_lines], start=1):
        lab = (s.get("type") or "step")[:32]
        ok = s.get("status") == "done"
        mark = "✅" if ok else "⏳"
        c = (s.get("command") or "")[:160]
        lines.append(f"{i}. {mark} {lab} — {c}")
    return "\n".join(lines).strip()


def _all_flow_steps_done(st: dict[str, Any]) -> bool:
    steps = st.get("steps") or []
    if not steps:
        return False
    return all(str(s.get("status") or "") == "done" for s in steps)


def format_workflow_complete_message(st: dict[str, Any]) -> str:
    """Shown when there are no pending steps or user asks for status at end of flow."""
    gl = (st.get("goal") or "this workflow").strip()[:200]
    lines: list[str] = [
        "Workflow complete.",
        f"Topic: {gl}",
        "Completed:",
    ]
    for s in (st.get("steps") or [])[:8]:
        lab = (s.get("type") or "step")[:32]
        c = (s.get("command") or "")[:100]
        lines.append(f"• {lab}: {c}")
    lines.append("Want to start a new workflow? Ask for next steps in chat, or a specific @agent or / command.")
    return "\n".join(lines).strip()


def _is_flow_info_query(t: str) -> bool:
    low = t.lower().strip()
    return bool(
        re.search(
            r"^(where are we\??|what('?s| is) (next|our status|left)\??|whats left\??|"
            r"status|progress|how far|what remains|what is left|what’s left|what's left)\b[!.?]*$",
            low,
        )
    )


def _is_flow_resume_phrase(t: str) -> bool:
    """Resume context without auto-running the next step."""
    low = t.lower().strip()
    if low in (
        "resume",
        "resume work",
        "continue where we left off",
        "continuing where we left off",
        "pick up where we left off",
    ):
        return True
    return bool(
        re.search(
            r"^(back to (the )?workflow|what were we (doing|working on))\b[!.?]*$",
            low,
        )
    )


def _is_flow_run_continuation_phrase(t: str) -> bool:
    low = t.lower().strip()
    if re.match(
        r"^next[!.?]*$|"
        r"^continue( with that)?[!.?]*$|"
        r"^proceed[!.?]*$|"
        r"^go ahead[!.?]*$|"
        r"^move on( to the next( step| one)?)?[!.?]*$|"
        r"^let'?s (go|do it)[!.?]*$",
        low,
    ):
        return True
    if re.search(
        r"^(do|run) (the )?next( one| step| thing)?( please)?[!.?]*$",
        low,
    ):
        return True
    return bool(re.search(r"^keep going[!.?]*$", low))


def append_adhoc_committed_action(cctx: ConversationContext, command: str) -> None:
    """
    If user ran a command that was not in the flow, append a single done step
    (keeps history continuous without a workflow engine).
    """
    c = (command or "").strip()
    if not c or not cctx:
        return
    st0 = _load_flow(cctx.current_flow_state_json)
    if st0 and _is_flow_expired(st0, now=datetime.now(timezone.utc)):
        cctx.current_flow_state_json = None
        st0 = None
    n = _norm_cmd(c)
    for s in (st0 or {}).get("steps") or []:
        if _norm_cmd(str(s.get("command") or "")) == n:
            st0 = st0 or {}
            st0["last_action"] = c[:1_200]
            st0["updated_at"] = _now_iso()
            cctx.current_flow_state_json = json.dumps(st0, ensure_ascii=False)
            return
    if st0 and (st0.get("steps") or []):
        step = {
            "index": len((st0.get("steps") or [])) + 1,
            "type": _step_type_from_command(c),
            "status": "done",
            "command": c[:1_200],
        }
        st0.setdefault("steps", []).append(step)
        st0["last_action"] = c[:1_200]
        st0["updated_at"] = _now_iso()
        cctx.current_flow_state_json = json.dumps(st0, ensure_ascii=False)
        return
    cctx.current_flow_state_json = json.dumps(
        {
            "goal": c[:200],
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "steps": [
                {
                    "index": 1,
                    "type": _step_type_from_command(c),
                    "status": "done",
                    "command": c[:1_200],
                }
            ],
            "last_action": c[:1_200],
        },
        ensure_ascii=False,
    )


def mark_flow_step_done(cctx: ConversationContext, command: str) -> None:
    c = (command or "").strip()
    if not c or not cctx or not cctx.current_flow_state_json:
        return
    st0 = _load_flow(cctx.current_flow_state_json)
    if not st0 or _is_flow_expired(st0, now=datetime.now(timezone.utc)):
        cctx.current_flow_state_json = None
        return
    n = _norm_cmd(c)
    for s in st0.get("steps") or []:
        if _norm_cmd(str(s.get("command") or "")) == n:
            s["status"] = "done"
    st0["last_action"] = c[:1_200]
    st0["updated_at"] = _now_iso()
    cctx.current_flow_state_json = json.dumps(st0, ensure_ascii=False)


def mark_flow_on_clear_reset_phrase(cctx: ConversationContext) -> None:
    cctx.current_flow_state_json = None


def interpret_flow_user_message(
    user_text: str,
    cctx: ConversationContext,
    *,
    now: datetime | None = None,
) -> FlowUserTurn:
    """Handle 'next' / 'where are we' when next_action_confirmation does not match."""
    now = now or datetime.now(timezone.utc)
    t = (user_text or "").strip()
    if not t:
        return FlowUserTurn()

    st = _load_flow(cctx.current_flow_state_json)
    tlow = t.lower().strip()
    if st and (
        re.search(
            r"(?i)^(start (over|fresh)|abandon( this| that)?( workflow| plan)?|"
            r"new plan|reset( flow| plan)?|forget (this|that) workflow)\b",
            tlow,
        )
        or tlow
        in ("new topic", "something else", "let's do something else")
    ):
        cctx.current_flow_state_json = None
        return FlowUserTurn(
            no_match=False,
            immediate_assistant="Okay — we can park that. What would you like to work on next?",
            clear_suggestions=True,
        )

    if not st:
        return FlowUserTurn()

    expired = _is_flow_expired(st, now=now)
    is_flowy = _is_flow_info_query(t) or _is_flow_run_continuation_phrase(t)
    if expired and is_flowy:
        cctx.current_flow_state_json = None
        return FlowUserTurn(
            no_match=False,
            immediate_assistant=(
                "I think we moved on from that workflow — what would you like to do next?"
            ),
            clear_suggestions=True,
        )
    if expired:
        if cctx.current_flow_state_json:
            cctx.current_flow_state_json = None
        return FlowUserTurn()

    if _is_flow_resume_phrase(t):
        pend = _pending_steps(st)
        gl = (st.get("goal") or "this work").strip()[:200]
        if not (st.get("steps") or []):
            return FlowUserTurn(
                no_match=False,
                immediate_assistant="No saved steps. Ask for next steps in chat, or a specific @agent or / command.",
            )
        if not pend and _all_flow_steps_done(st):
            return FlowUserTurn(
                no_match=False,
                immediate_assistant=format_workflow_complete_message(st),
            )
        if not pend:
            return FlowUserTurn(
                no_match=False,
                immediate_assistant=(
                    f"{format_flow_bullet_summary(st)}\n\n"
                    "Pick the next action, or ask for a refreshed next-steps list."
                ),
            )
        n0 = (pend[0].get("command") or "").strip()[:500]
        return FlowUserTurn(
            no_match=False,
            immediate_assistant=(
                f"You were working on: {gl}\n"
                f"Next: {n0}\n\n"
                'Reply “next” to run that step, or type a different command. I will not run it until you say so.'
            ),
        )

    if _is_flow_info_query(t):
        pend = _pending_steps(st)
        if not pend and _all_flow_steps_done(st):
            return FlowUserTurn(
                no_match=False,
                immediate_assistant=format_workflow_complete_message(st),
            )
        if not pend:
            return FlowUserTurn(
                no_match=False,
                immediate_assistant=(
                    f"{format_flow_bullet_summary(st)}\n\n"
                    "No pending step here — name the next action, or ask a new question."
                ),
            )
        if len(pend) == 1:
            c0 = (pend[0].get("command") or "").strip()
            rsk = risk_for_suggestion_command(c0)[:20]
            return FlowUserTurn(
                no_match=False,
                immediate_assistant=(
                    f"{format_flow_bullet_summary(st)}\n\n"
                    f"Next in queue: {c0} (risk: {rsk}). "
                    f"Reply “next” or paste that line when you are ready."
                ),
            )
        return FlowUserTurn(
            no_match=False,
            immediate_assistant=(
                f"{format_flow_bullet_summary(st)}\n\n"
                f"{len(pend)} steps are available — which first? "
                f"Reply 1 / 2, name the agent, or ask to refresh the next-step list."
            ),
        )

    if not _is_flow_run_continuation_phrase(t):
        return FlowUserTurn()

    pend = _pending_steps(st)
    if not pend:
        if _all_flow_steps_done(st):
            return FlowUserTurn(
                no_match=False,
                immediate_assistant=format_workflow_complete_message(st),
            )
        return FlowUserTurn(
            no_match=False,
            immediate_assistant=(
                f"{format_flow_bullet_summary(st)}\n\n"
                "Nothing in the next-step queue. Ask for a new plan, or a specific @agent or / command."
            ),
        )
    if len(pend) > 1:
        return FlowUserTurn(
            no_match=False,
            immediate_assistant=(
                f"{format_flow_bullet_summary(st)}\n\n"
                "Several steps are next — which one? Reply 1 / 2, or name the one you want (e.g. the research one)."
            ),
        )
    cmd = (pend[0].get("command") or "").strip()
    if not cmd:
        return FlowUserTurn()
    if not is_injectable_command(cmd):
        short = cmd[:500] + ("…" if len(cmd) > 500 else "")
        return FlowUserTurn(
            no_match=False,
            immediate_assistant=(
                f"I can send this as your next chat line (same as pasting it yourself):\n\n"
                f"`{short}`\n\n"
                f"Reply **`run` once** to continue, or paste the line if you prefer."
            ),
            store_pending_freeform=cmd,
            clear_suggestions=True,
        )
    return FlowUserTurn(
        no_match=False,
        reprocess_user_text=cmd,
        ack_line=ack_line_for_injected_command(cmd),
        clear_suggestions=True,
    )
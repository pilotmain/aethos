"""
Deterministic @boss routes for runtime tools (before LLM fallback).

Handles must appear as @handle in the user message; goal is inferred from the remainder.

Boss-runtime invariant: when this function is used, the turn is already routed to the boss
agent (mention / boss key). If the body also has bounded-mission vocabulary and non-boss
@handles, we call sessions_spawn and return — **do not** fall through to the LLM.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.agent_runtime.chat_tools import (
    bounded_mission_signals_present,
    detect_bounded_mission_structure,
    detect_valid_bounded_mission,
    format_sessions_spawn_result,
    mission_payload_for_spawn,
    try_record_initial_spawn_heartbeat,
)
from app.services.agent_runtime.heartbeat import background_heartbeat
from app.services.agent_runtime.sessions import sessions_spawn
from app.services.agent_runtime.tool_registry import load_tool_manifest
from app.services.audit_service import audit
from app.services.custom_agents import (
    display_agent_handle,
    normalize_agent_key,
)
from app.services.mission_control.mode import (
    handle_mission_control_dashboard_turn,
    is_mission_control_mode_prompt,
)
from app.services.runtime_capabilities import log_guardrail_block

logger = logging.getLogger(__name__)

_BOSS_KEY = "boss"

_MIN_GOAL_LEN = 5

_RE_RECURRING = re.compile(
    r"(?is)\b("
    r"every\s+\d+\s*(?:hours?|hrs?)|"
    r"\bevery\s+hour\b|"
    r"every\s+12\s+hours|"
    r"repeat\s+automatically|"
    r"recurring(?:ly)?|"
    r"autonomously\s+forever|"
    r"\bforever\b"
    r")\b"
)

_RE_UNSUPERVISED = re.compile(
    r"(?is)\b("
    r"overnight|"
    r"all\s+night|"
    r"without\s+(?:my\s+)?involvement|"
    r"without\s+asking\s+me|"
    r"without\s+me|"
    r"without\s+you"
    r")\b"
)

_RE_UNBOUNDED_AUTONOMY = re.compile(
    r"(?is).*\b(overnight|all\s+night|24\s*[- ]?hour|without\s+(my\s+)?involvement|autonomously)\b.*"
)

# Bounded supervised spawn — expanded phrases (do not send these to the LLM first).
_RE_SPAWN_TRIGGER = re.compile(
    r"(?is)\b(?:"
    r"bounded\s+agent\s+swarm|"
    r"agent\s+swarm|"
    r"spawn\s+sessions|"
    r"spawn\s+with\b|"
    r"spawn\s+(?:a\s+)?(?:bounded\s+)?(?:agent\s+)?sessions|"
    r"create\s+(?:a\s+)?(?:bounded\s+)?(?:agent\s+)?sessions|"
    r"create\s+agent\s+sessions|"
    r"create\s+(?:a\s+)?(?:bounded\s+)?(?:agent\s+)?swarm\b|"
    r"start\s+(?:a\s+)?(?:bounded\s+)?supervised\s+sessions|"
    r"create\s+a\s+bounded\s+session|"
    r"bounded\s+session\b|"
    r"sessions_spawn\s*\(|"
    r"\binvoke\s+sessions_spawn\b|"
    r"\binvoking\s+sessions_spawn\b|"
    r"\bexecute\s+(?:a\s+)?bounded\s+mission\b"
    r")\b"
)

_RE_FILE_POLICY_TAIL = re.compile(
    r"(?is)(?:[.\s]*)(?:do\s+not\s+write\s+files|no\s+file\s+writes|read[- ]only)\.?\s*$"
)

_RE_SPAWN_HEX_ID = re.compile(r"\b(spawn_[a-fA-F0-9]{6,24})\b")


def extract_spawn_group_id_for_chat(text: str) -> str | None:
    m = _RE_SPAWN_HEX_ID.search(text or "")
    return m.group(1) if m else None


def has_spawn_lifecycle_intent(text: str) -> bool:
    """True when text references a spawn id *and* orchestration-style verbs (public API for routing)."""
    m = (text or "").strip()
    return extract_spawn_group_id_for_chat(m) is not None and _is_spawn_lifecycle_intent(m)


def _is_spawn_lifecycle_intent(text: str) -> bool:
    low = (text or "").lower()
    if re.search(r"(?is)\bcontinue\b", low):
        return True
    if re.search(r"(?is)\bstatus\s+(?:of|for)\b", low):
        return True
    if "what is happening" in low or "what's happening" in low:
        return True
    if re.search(r"(?is)spawn_group_id\s*[:=]", low):
        return True
    if "assignment_ids" in low and _RE_SPAWN_HEX_ID.search(text or ""):
        return True
    return False


def try_spawn_lifecycle_chat_turn(
    db: Session,
    app_user_id: str,
    message: str,
) -> str | None:
    """
    Deterministic spawn-group lookup / continue — runs before agent personas when message
    references a spawn_group_id with orchestration intent (continue, status, assignment dump).
    """
    m = (message or "").strip()
    if not m:
        return None
    sgid = extract_spawn_group_id_for_chat(m)
    if not sgid:
        return None
    if not _is_spawn_lifecycle_intent(m):
        return None

    from app.services.agent_runtime.spawn_state import (
        continue_spawn_group,
        get_spawn_group_state,
    )

    uid = (app_user_id or "").strip()[:64]
    low = m.lower()
    is_continue = bool(re.search(r"(?is)\bcontinue\b", low))

    state = get_spawn_group_state(db, user_id=uid, spawn_group_id=sgid)
    if not state.get("ok"):
        return f"I could not find spawn group **`{sgid}`**."

    def _assignment_lines(st: dict[str, Any]) -> list[str]:
        out: list[str] = []
        for a in st.get("assignments") or []:
            ah = display_agent_handle(str(a.get("assigned_to_handle") or ""))
            out.append(f"- **#{a['id']}** `{ah}` — **{a['status']}**")
        return out

    def _aggregate_status(summary: dict[str, int]) -> str:
        if not summary:
            return "unknown"
        if summary.get("running", 0):
            return "running"
        if summary.get("queued", 0):
            return "queued"
        parts = [f"{k}:{v}" for k, v in sorted(summary.items()) if v]
        return ", ".join(parts) if parts else "unknown"

    if is_continue:
        if not get_settings().nexa_agent_tools_enabled:
            return (
                f"I found **`{state['spawn_group_id']}`**.\n\n"
                "Assignments:\n"
                + "\n".join(_assignment_lines(state))
                + "\n\nGoal:\n"
                + (state.get("goal") or "(could not infer from titles)")
                + "\n\n**Runtime tools are disabled** — enable **`NEXA_AGENT_TOOLS_ENABLED=true`** to record a "
                "continuation heartbeat."
            )[:12_000]
        _audit_tool_chat(db, user_id=uid, tool="background_heartbeat")
        try:
            out = continue_spawn_group(db, user_id=uid, spawn_group_id=str(state["spawn_group_id"]))
            hb = out.get("heartbeat") or {}
            lines = [
                f"I found **`{out['spawn_group_id']}`**.",
                "",
                "Assignments:",
                *_assignment_lines(out),
                "",
                "Goal:",
                out.get("goal") or "(unknown)",
                "",
                f"Heartbeat recorded for **{display_agent_handle('boss')}**.",
                "",
                "**Mission Control report updated** (file-backed).",
                "",
                f"_`{hb.get('recorded_at', '')}`_",
            ]
            return "\n".join(lines)[:12_000]
        except Exception as exc:  # noqa: BLE001
            logger.exception("continue_spawn_group: %s", exc)
            return f"I could not continue the spawn group: {exc!s}"[:2000]

    summ = state.get("summary") or {}
    agg = _aggregate_status(summ)
    lines = [
        f"Spawn group **`{state['spawn_group_id']}`**",
        "",
        f"**Overall:** {agg}",
        "",
        "Assignments:",
        *_assignment_lines(state),
        "",
        "Goal:",
        state.get("goal") or "(could not infer from titles)",
    ]
    return "\n".join(lines)[:12_000]


def is_boss_agent_key(agent_key: str) -> bool:
    return normalize_agent_key(agent_key or "") == _BOSS_KEY


def format_tools_list_reply() -> str:
    """Deterministic reply for 'what tools do you have?'"""
    if not get_settings().nexa_agent_tools_enabled:
        return (
            "**Runtime tools are not enabled** for **@boss** in this workspace.\n\n"
            "Set **`NEXA_AGENT_TOOLS_ENABLED=true`** (and restart the API) to enable governed "
            "`sessions_spawn` and `background_heartbeat`."
        )
    man = load_tool_manifest()
    lines = []
    for t in man.get("tools") or []:
        if not t.get("enabled", True):
            continue
        nm = (t.get("name") or "").strip()
        if not nm:
            continue
        desc = (t.get("description") or "").strip()
        lines.append(f"- **{nm}** — {desc}" if desc else f"- **{nm}**")
    if not lines:
        return (
            "Runtime tools are enabled, but **agent_tools.json** has no enabled entries. "
            "Check your workspace **config/agent_tools.json**."
        )
    return "Available governed tools:\n" + "\n".join(lines)


def _extract_handles_excluding_boss(text: str) -> list[str]:
    found = re.findall(r"@([\w-]{2,64})\b", text or "")
    out: list[str] = []
    for h in found:
        hk = normalize_agent_key(h)
        if hk == _BOSS_KEY:
            continue
        if hk and hk not in out:
            out.append(hk)
    return out


def _strip_spawn_file_policy(text: str) -> str:
    s = (text or "").strip()
    s = _RE_FILE_POLICY_TAIL.sub("", s).strip()
    return s


def _parse_spawn_goal(text: str) -> str | None:
    """Return a goal string suitable for sessions_spawn, or None if the user did not state one."""
    t = _strip_spawn_file_policy(text)
    m = re.search(r"(?is)\bto\s+(.+)$", t)
    if m:
        g = _strip_spawn_file_policy(m.group(1)).strip()
        if len(g) >= _MIN_GOAL_LEN:
            return g[:2000]
    m = re.search(r"(?is)\bfor\s+(.+)$", t)
    if m:
        g = _strip_spawn_file_policy(m.group(1)).strip()
        if len(g) >= _MIN_GOAL_LEN:
            return g[:2000]
    m = re.search(
        r"(?is)\b(investigate|research|analyze|analyse|study|explore)\s+(.+)$",
        t,
    )
    if m:
        g = f"{m.group(1)} {m.group(2)}".strip()
        g = _strip_spawn_file_policy(g).strip()
        if len(g) >= _MIN_GOAL_LEN:
            return g[:2000]
    return None


def _is_tools_question(text: str) -> bool:
    t = (text or "").strip().lower()
    if "what tools" in t or "which tools" in t:
        return True
    if "tools do you have" in t or "tools you have" in t:
        return True
    return "available tools" in t and "?" in t


def _infer_heartbeat_status_from_text(message: str) -> str:
    low = (message or "").lower()
    if re.search(r"\b(blocked|stuck)\b", low):
        return "blocked"
    if re.search(r"\b(waiting|pending\s+approval)\b", low):
        return "waiting_approval"
    if re.search(r"\b(failed|error)\b", low):
        return "failed"
    if re.search(r"\b(cancelled|canceled)\b", low):
        return "cancelled"
    if re.search(r"\b(done|complete|completed|finished)\b", low):
        return "completed"
    if re.search(r"\b(queued|queue)\b", low):
        return "queued"
    return "running"


def _parse_heartbeat_message(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    low = raw.lower()
    if low.startswith("record heartbeat"):
        rest = raw.split(":", 1)[1].strip() if ":" in raw else ""
        if not rest:
            return None
        st = _infer_heartbeat_status_from_text(rest)
        return {"status": st, "message": rest[:2000]}
    if low.startswith("heartbeat:"):
        rest = raw.split(":", 1)[1].strip()
        if not rest:
            return None
        st = _infer_heartbeat_status_from_text(rest)
        return {"status": st, "message": rest[:2000]}
    m = re.match(
        r"(?is)^heartbeat\s+(queued|running|waiting_approval|blocked|completed|failed|cancelled)\s+(.+)$",
        raw,
    )
    if m:
        return {"status": m.group(1), "message": m.group(2).strip()[:2000]}
    m = re.match(
        r"(?is)^update\s+heartbeat\s*:\s*(queued|running|blocked|waiting_approval|completed|failed)?\s*(.+)$",
        raw,
    )
    if m:
        st = (m.group(1) or "").strip().lower()
        msg = (m.group(2) or "").strip()
        if not msg:
            return None
        status = st if st in {
            "queued",
            "running",
            "blocked",
            "waiting_approval",
            "completed",
            "failed",
        } else _infer_heartbeat_status_from_text(msg)
        return {"status": status, "message": msg[:2000]}
    return None


def _audit_tool_chat(db: Session, *, user_id: str, tool: str) -> None:
    audit(
        db,
        event_type="agent_runtime.tool_invoked",
        actor="aethos",
        user_id=user_id,
        message=f"Chat invoked {tool}",
        metadata={"tool": tool, "agent_handle": "boss", "source": "chat"},
    )


def _runtime_tools_disabled_reply() -> str:
    return format_tools_list_reply()


def try_boss_runtime_chat_turn(
    db: Session,
    app_user_id: str,
    message: str,
) -> str | None:
    """
    If message matches a deterministic boss runtime pattern, run tools and return the reply.
    Otherwise return None (caller runs LLM).
    """
    uid = (app_user_id or "").strip()[:64]
    m = (message or "").strip()
    if not m:
        return None

    if _is_tools_question(m):
        return format_tools_list_reply()

    life = try_spawn_lifecycle_chat_turn(db, uid, m)
    if life is not None:
        return life

    # Mission Control dashboard / UI configuration — never sessions_spawn.
    if is_mission_control_mode_prompt(m):
        inner_dm = detect_bounded_mission_structure(m)
        return handle_mission_control_dashboard_turn(db, uid, m, inner_mission=inner_dm)

    hb = _parse_heartbeat_message(m)
    if hb is not None and get_settings().nexa_agent_tools_enabled:
        _audit_tool_chat(db, user_id=uid, tool="background_heartbeat")
        try:
            payload = {
                "agent_handle": "boss",
                "assignment_id": None,
                "status": hb["status"],
                "message": hb["message"],
            }
            background_heartbeat(db, user_id=uid, payload=payload)
            return (
                f"Heartbeat recorded for **{display_agent_handle('boss')}**.\n\n"
                f"Status: **{hb['status']}**\n\n"
                f"Mission Control report updated (file-backed).\n\n"
                f"_{hb['message'][:400]}_"
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("boss heartbeat: %s", exc)
            return f"I could not record heartbeat: {exc!s}"[:2000]
    elif hb is not None and not get_settings().nexa_agent_tools_enabled:
        return _runtime_tools_disabled_reply()

    # Recurring unsupervised autonomy — refuse without invoking spawn.
    if _RE_RECURRING.search(m) and _RE_UNSUPERVISED.search(m):
        log_guardrail_block(
            "recurring_unsupervised_autonomy",
            detail="recurring+unsupervised patterns in boss message",
            extra={"user_id": uid},
        )
        return (
            "I **cannot** run unrestricted recurring autonomous work.\n\n"
            "I **can** create a **bounded, supervised** session **now**, or help you define a "
            "scheduled task that **requires approval**."
        )

    if _RE_UNBOUNDED_AUTONOMY.search(m) and re.search(
        r"(?is)(autonomous|autonomously|overnight|all\s+night|without)", m
    ):
        log_guardrail_block(
            "unbounded_autonomy_overnight",
            detail="overnight/unbounded autonomy patterns",
            extra={"user_id": uid},
        )
        return (
            "I can create **bounded, supervised** agent sessions with a **timebox** and **approval policy** — "
            "not unrestricted autonomous work.\n\n"
            "I **cannot** run agents autonomously all night without your involvement in this build.\n\n"
            "I can record **heartbeats** when you ask (e.g. **heartbeat: …** or **record heartbeat: …**), but I "
            "**cannot** schedule recurring background heartbeats unless a host scheduler is configured."
        )

    # If deterministic validation succeeds, do not send this turn to the LLM.
    # The LLM may format results only after the backend tool has returned.
    mission = detect_valid_bounded_mission(m)
    if mission is not None:
        if not get_settings().nexa_agent_tools_enabled:
            return _runtime_tools_disabled_reply()
        payload_mb = mission_payload_for_spawn(user_id=uid, mission=mission)
        _audit_tool_chat(db, user_id=uid, tool="sessions_spawn")
        try:
            out = sessions_spawn(db, user_id=uid, payload=payload_mb)
            logger.info(
                "tool_execution tool=sessions_spawn user_id=%s spawn_group_id=%s "
                "assignment_ids=%s mission_contract=%s",
                uid,
                out.get("spawn_group_id"),
                [a.get("assignment_id") for a in (out.get("assignments") or [])],
                bool(payload_mb.get("mission_contract")),
            )
            init_hb = try_record_initial_spawn_heartbeat(
                db,
                user_id=uid,
                spawn_group_id=str(out.get("spawn_group_id") or ""),
                recurring_requested=bool(mission.get("heartbeat_recurring_requested")),
            )
            return format_sessions_spawn_result(
                out,
                initial_heartbeat_note=init_hb,
                recurring_heartbeat_note=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("boss sessions_spawn (bounded mission): %s", exc)
            logger.info(
                "tool_execution tool=sessions_spawn user_id=%s ok=False error=%s",
                uid,
                str(exc)[:500],
            )
            return f"Could not create bounded mission: {exc!s}"[:2000]

    # Boss channel + bounded vocabulary + @handles → deterministic spawn (no LLM).
    # Routed boss turns often omit a literal "@boss" in the body (mention stripped).
    spawn_hit = bool(
        _RE_SPAWN_TRIGGER.search(m)
        or (
            bounded_mission_signals_present(m) and bool(_extract_handles_excluding_boss(m))
        )
    )
    if spawn_hit:
        if not get_settings().nexa_agent_tools_enabled:
            return _runtime_tools_disabled_reply()

        handles = _extract_handles_excluding_boss(m)
        if not handles:
            return (
                "Which agents should I include? Example: **@research-analyst** and **@qa**."
            )

        parsed_goal = _parse_spawn_goal(m)
        goal = parsed_goal
        if goal is None:
            return "What should the mission goal be?"

        sessions: list[dict[str, Any]] = []
        for i, h in enumerate(handles):
            if len(handles) == 1:
                task = goal
            elif i == 0:
                task = f"{goal} — focus area for {display_agent_handle(h)}"
            elif i == 1:
                task = f"Review findings and identify gaps for: {goal}"
            else:
                task = f"{goal} — focus area for {display_agent_handle(h)}"
            role = "Reviewer" if (len(handles) > 1 and i == 1) else "Worker"
            sessions.append(
                {
                    "agent_handle": h,
                    "role": role,
                    "task": task[:2000],
                }
            )

        payload: dict[str, Any] = {
            "requested_by": uid,
            "goal": goal,
            "sessions": sessions,
            "timebox_minutes": 60,
            "approval_policy": {
                "mode": "plan_only",
                "allow_file_read": False,
                "allow_file_write": False,
                "allow_shell": False,
                "allow_network": False,
                "allow_git": False,
            },
        }

        _audit_tool_chat(db, user_id=uid, tool="sessions_spawn")
        try:
            out = sessions_spawn(db, user_id=uid, payload=payload)
            logger.info(
                "tool_execution tool=sessions_spawn user_id=%s spawn_group_id=%s "
                "assignment_ids=%s payload_sessions=%s",
                uid,
                out.get("spawn_group_id"),
                [a.get("assignment_id") for a in (out.get("assignments") or [])],
                [{"h": s.get("agent_handle"), "role": s.get("role")} for s in sessions],
            )
            hb_note = try_record_initial_spawn_heartbeat(
                db,
                user_id=uid,
                spawn_group_id=str(out.get("spawn_group_id") or ""),
                recurring_requested=False,
            )
            return format_sessions_spawn_result(out, initial_heartbeat_note=hb_note)
        except Exception as exc:  # noqa: BLE001
            logger.exception("boss sessions_spawn: %s", exc)
            logger.info(
                "tool_execution tool=sessions_spawn user_id=%s ok=False error=%s",
                uid,
                str(exc)[:500],
            )
            return f"I could not create the session group: {exc!s}"[:2000]

    return None

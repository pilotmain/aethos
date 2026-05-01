"""
Structured bounded-mission detection for deterministic sessions_spawn (no LLM confirmation loop).

Invariant: if detect_valid_bounded_mission() returns a dict, the caller should execute sessions_spawn
and return formatted results — do not send this turn to the LLM for approval.

Boss chat (try_boss_runtime_chat_turn): bounded mission vocabulary plus non-boss @handles also
forces sessions_spawn without the LLM (see boss_chat.spawn_hit).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.custom_agents import display_agent_handle, normalize_agent_key
from app.services.swarm.mission_parser import parse_mission

logger = logging.getLogger(__name__)

# Must read as a governed, bounded, supervised mission (not a vague “research something”).
_RE_BOUNDED_SIGNAL = re.compile(
    r"(?is)"
    r"\bsingle[- ]?cycle\b|"
    r"\bhuman\s+oversight\b|"
    r"\bexplicit\s+(?:human\s+)?oversight\b|"
    r"\bgoverned\s+runtime\b|"
    r"\bauthorization\s*(?:&|and)?\s*scope\b|"
    r"\bteam\s+initialization\b|"
    r"\bbounded\s*,\s*single[- ]?cycle\b|"
    r"\bsupervised\s*,\s*bounded\b|"
    r"\bbounded\s*,\s*supervised\b|"
    r"\bbounded\s+mission\b|"
    r"\bdeveloper[- ]mode\b|"
    r"\bsupervised\s+mission\b"
)


def bounded_mission_signals_present(text: str) -> bool:
    """True when text uses governed/bounded mission vocabulary (aligned with spawn detection)."""
    return bool(_RE_BOUNDED_SIGNAL.search((text or "").strip()))

_RE_SPAWN_OR_MISSION = re.compile(
    r"(?is)"
    r"sessions_spawn\s*\(|"
    r"\buse\s+sessions_spawn\b|"
    r"\bexecute\s+system\s+mission\b|"
    r"\bexecute\s+bounded\s+mission\b|"
    r"\bteam\s+initialization\b|"
    r"@boss\s+run\s+mission\b|"
    r"\brun\s+mission\b"
)

_RE_GOAL_QUOTED = re.compile(
    r'(?is)(?:execute\s+)?System\s+Mission:\s*"([^"]+)"|Mission:\s*"([^"]+)"|'
    r'\bSystem\s+Mission\s+"([^"]+)"'
)

# Per-agent lines: "@researcher-pro: task" or "@researcher-pro : task" (multiline document).
_RE_AGENT_TASK_LINE = re.compile(
    r"(?im)^\s*@([\w-]{2,64})\s*:\s*(.+)$",
)

_RE_OUTPUT_PATH = re.compile(r"(?i)(/[\w./-]+\.(?:json|md|txt))\b")

_RE_HEARTBEAT_RECURRING = re.compile(
    r"(?is)(?:record\s+)?(?:background_heartbeat|heartbeat)\s+(?:every|each)\s+\d+\s*(?:hour|hr|minute|min)s?\b"
)

# `@` is not a \\w char — avoid leading \\b before `@` (fails after newline / punctuation).
_RE_BOSS_MENTION = re.compile(r"(?i)(?<!\w)@boss\b")

_RE_EXECUTE_BOUNDED_SHORT = re.compile(r"(?is)\bexecute\s+bounded\s+mission\b")


def _handles_after_with_clause(text: str) -> list[str]:
    """Parse `@a and @b` / `@a, @b` after the phrase `with`."""
    raw = text or ""
    low = raw.lower()
    if " with " not in low and not re.search(r"(?is)\bwith\s+@", raw):
        return []
    m = re.search(
        r"(?is)\bwith\s+(.+?)(?:\.?\s*$|\n\n|\n(?=[A-Z#]))",
        raw,
    )
    if not m:
        return []
    tail = m.group(1)
    found = re.findall(r"(?<!\w)@([\w-]{2,64})\b", tail)
    out: list[str] = []
    for h in found:
        hk = normalize_agent_key(h)
        if hk == "boss":
            continue
        if hk and hk not in out:
            out.append(hk)
    return out


def _agents_from_short_bounded_form(raw: str) -> list[dict[str, str]]:
    """`@boss execute bounded mission with @a and @b` — generic tasks per agent."""
    if not _RE_EXECUTE_BOUNDED_SHORT.search(raw):
        return []
    handles = _handles_after_with_clause(raw)
    if len(handles) < 1:
        return []
    rows: list[dict[str, str]] = []
    for hk in handles[:10]:
        rows.append(
            {
                "agent_handle": hk,
                "task": f"Execute your assigned part of this bounded supervised mission (coordinate with other agents as needed).",
            }
        )
    return rows


def _extract_goal(text: str) -> str | None:
    m = _RE_GOAL_QUOTED.search(text or "")
    if m:
        for g in m.groups():
            if g and len(g.strip()) >= 5:
                return g.strip()[:2000]
    return None


_BOILER_HEADING_LINE = re.compile(
    r"(?is)^\s*(?:#{1,6}\s*)?(?:dashboard|instruction|instructions|mission control|"
    r"workflow|authorization|team initialization|heartbeat|scope)\b\s*[:\-]?\s*$"
)


def clean_task_for_spawn(task: str) -> str:
    """
    Remove leading dashboard / instruction section headers so titles are not huge prose blocks.
    Keeps the first substantive task lines.
    """
    raw = (task or "").strip()
    if not raw:
        return ""
    kept: list[str] = []
    for line in raw.splitlines():
        t = line.strip()
        if not t:
            if kept:
                break
            continue
        if _BOILER_HEADING_LINE.match(t):
            continue
        if re.match(r"(?i)^\s*(?:#{1,6}\s+)?(?:workflow|dashboard)\b", t):
            continue
        kept.append(t)
    out = "\n".join(kept).strip()
    return (out or raw)[:2000]


def short_assignment_title(task_or_goal: str, *, max_len: int = 220) -> str:
    """Single-line title for AgentAssignment — never the full mission markdown."""
    base = clean_task_for_spawn(task_or_goal)
    first = (base.split("\n")[0] or "").strip()
    if len(first) < 12 and "\n" in base:
        first = "\n".join(x.strip() for x in base.split("\n")[:2] if x.strip())
    one = re.sub(r"\s+", " ", first).strip()
    if len(one) > max_len:
        one = one[: max_len - 1].rstrip() + "…"
    return one or "Assignment"


def dedupe_session_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same spawn: one row per agent_handle (last task wins); preserves first-seen order."""
    order: list[str] = []
    by_handle: dict[str, dict[str, Any]] = {}
    for spec in specs or []:
        h = normalize_agent_key(str(spec.get("agent_handle") or ""))
        if not h or h == "boss":
            continue
        task = clean_task_for_spawn(str(spec.get("task") or ""))
        if len(task) < 5:
            continue
        if h not in by_handle:
            order.append(h)
        role = str(spec.get("role") or "").strip() or "Worker"
        deps_raw = spec.get("depends_on") or []
        deps: list[str] = []
        if isinstance(deps_raw, list):
            for d in deps_raw:
                dk = normalize_agent_key(str(d))
                if dk and dk not in deps:
                    deps.append(dk)
        row = {"agent_handle": h, "role": role, "task": task[:2000]}
        if deps:
            row["depends_on"] = deps
        by_handle[h] = row
    return [by_handle[h] for h in order if h in by_handle]


def _extract_agent_tasks(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for m in _RE_AGENT_TASK_LINE.finditer(text or ""):
        hk = normalize_agent_key(m.group(1))
        if hk == "boss":
            continue
        task = clean_task_for_spawn((m.group(2) or "").strip())
        if len(task) >= 5:
            rows.append({"agent_handle": hk, "task": task[:2000]})
    return rows


def _strip_visual_dashboard_noise(text: str) -> str:
    """Remove illustrative [MISSION] / visual-formatting blocks so they are not parsed as tasks."""
    raw = text or ""
    raw = re.sub(r"(?is)^\s*visual\s+formatting\s*:.*?(?=^\s*(?:\[MISSION\]|@boss|\Z))", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"(?is)\[MISSION\]\s*\n.*?(?=^\s*(?:\[|@boss|authorization|team\s+initialization|\Z))", "", raw, flags=re.MULTILINE)
    return raw.strip()


_CONFIG_LAYOUT_SIGNALS = re.compile(
    r"(?is)\b(?:behavior\s+rules|visual\s+formatting|watchlist\s+behavior|"
    r"organize\s+output|structure\s+responses)\b"
)


def _dominant_configuration_without_spawn_ritual(raw: str) -> bool:
    """Fix 5 — layout/config signals without explicit bounded spawn ritual."""
    hits = len(_CONFIG_LAYOUT_SIGNALS.findall(raw))
    if hits < 2:
        return False
    if re.search(r"(?is)\bexecute\s+(?:a\s+)?bounded\s+mission\b", raw):
        return False
    if re.search(r"(?is)(?:\bsessions_spawn\s*\(|\buse\s+sessions_spawn\b)", raw):
        return False
    if re.search(r"(?is)\bexecute\s+system\s+mission\b", raw):
        return False
    return True


def detect_bounded_mission_structure(text: str) -> dict[str, Any] | None:
    """
    Raw bounded-mission parse (no Mission Control dashboard-mode filter).
    """
    raw = _strip_visual_dashboard_noise((text or "").strip())
    short_bounded = bool(_RE_EXECUTE_BOUNDED_SHORT.search(raw))

    # Strict mission document: quoted title + per-agent task lines (see swarm/mission_parser.py).
    pm = parse_mission(raw)
    if pm is not None and _RE_BOSS_MENTION.search(raw):
        if pm.get("single_cycle") or bounded_mission_signals_present(raw):
            agents_pm: list[dict[str, str]] = []
            for t in pm.get("tasks") or []:
                if not isinstance(t, dict):
                    continue
                hk = normalize_agent_key(str(t.get("agent_handle") or ""))
                if not hk or hk == "boss":
                    continue
                task = clean_task_for_spawn(str(t.get("task") or "").strip())
                if len(task) < 5:
                    continue
                row: dict[str, Any] = {"agent_handle": hk, "task": task[:2000]}
                deps = t.get("depends_on") or []
                if isinstance(deps, list) and deps:
                    row["depends_on"] = [normalize_agent_key(str(x)) for x in deps if str(x).strip()]
                agents_pm.append(row)
            goal_pm = str(pm.get("title") or "").strip()
            if agents_pm and goal_pm and len(goal_pm) >= 2:
                output_paths: list[str] = []
                for m in _RE_OUTPUT_PATH.finditer(raw):
                    p = m.group(1).strip()
                    if p not in output_paths:
                        output_paths.append(p[:512])
                hb_recurring = bool(_RE_HEARTBEAT_RECURRING.search(raw))
                return {
                    "tool": "sessions_spawn",
                    "goal": goal_pm[:2000],
                    "sessions_specs": agents_pm,
                    "output_paths": output_paths,
                    "heartbeat_recurring_requested": hb_recurring,
                    "timebox_minutes": 60,
                    "strict_mission_parser": True,
                }

    min_len = 28 if short_bounded else 40
    if len(raw) < min_len:
        return None
    if not _RE_BOSS_MENTION.search(raw):
        return None
    if not _RE_BOUNDED_SIGNAL.search(raw):
        return None
    if not _RE_SPAWN_OR_MISSION.search(raw):
        return None
    goal = _extract_goal(raw)
    agents = _extract_agent_tasks(raw)
    if not agents:
        agents = _agents_from_short_bounded_form(raw)
    if not goal or len(goal) < 5:
        if short_bounded and agents:
            goal = "Bounded supervised mission (short form)."
        else:
            return None
    if not agents:
        return None
    output_paths: list[str] = []
    for m in _RE_OUTPUT_PATH.finditer(raw):
        p = m.group(1).strip()
        if p not in output_paths:
            output_paths.append(p[:512])
    hb_recurring = bool(_RE_HEARTBEAT_RECURRING.search(raw))
    return {
        "tool": "sessions_spawn",
        "goal": goal,
        "sessions_specs": agents,
        "output_paths": output_paths,
        "heartbeat_recurring_requested": hb_recurring,
        "timebox_minutes": 60,
    }


def detect_valid_bounded_mission(text: str) -> dict[str, Any] | None:
    """
    Return a mission descriptor when the message is a complete bounded supervised spawn request.

    Rejects Mission Control *dashboard configuration* prompts and dominant layout-only drafts.
    """
    raw = (text or "").strip()
    inner = detect_bounded_mission_structure(raw)
    if inner is None:
        return None
    if _dominant_configuration_without_spawn_ritual(raw):
        return None
    from app.services.mission_control.mode import is_mission_control_mode_prompt

    if is_mission_control_mode_prompt(raw):
        return None
    return inner


def format_sessions_spawn_result(
    result: dict[str, Any],
    *,
    initial_heartbeat_note: str | None = None,
    recurring_heartbeat_note: str | None = None,
) -> str:
    """User-facing block after a real sessions_spawn result dict."""
    lines = [
        f"Spawn group created: **`{result['spawn_group_id']}`**",
        "",
        "Assignments:",
    ]
    for a in result.get("assignments") or []:
        ah = str(a.get("agent_handle") or "")
        lines.append(
            f"- **#{a['assignment_id']}** `{display_agent_handle(ah)}` — **{a['status']}**"
        )
    lines.append("")
    if initial_heartbeat_note:
        lines.append(initial_heartbeat_note)
    if recurring_heartbeat_note:
        lines.append(recurring_heartbeat_note)
    lines.extend(
        [
            "**Mission Control report updated** (file-backed).",
        ]
    )
    return "\n".join(lines)[:12_000]


def mission_payload_for_spawn(
    *,
    user_id: str,
    mission: dict[str, Any],
) -> dict[str, Any]:
    """Build validate_sessions_spawn payload from detect_valid_bounded_mission output."""
    uid = (user_id or "").strip()[:64]
    raw_specs = mission.get("sessions_specs") or []
    specs = dedupe_session_specs([dict(x) for x in raw_specs])
    goal = clean_task_for_spawn(str(mission.get("goal") or "").strip()) or str(
        mission.get("goal") or ""
    ).strip()[:2000]
    sessions: list[dict[str, Any]] = []
    for i, spec in enumerate(specs):
        h = str(spec.get("agent_handle") or "").strip()
        task = str(spec.get("task") or "").strip()
        role = "Reviewer" if (len(specs) > 1 and i == 1) else "Worker"
        sess: dict[str, Any] = {
            "agent_handle": h,
            "role": role,
            "task": task[:2000],
        }
        deps = spec.get("depends_on") if isinstance(spec, dict) else None
        if isinstance(deps, list) and deps:
            sess["depends_on"] = [normalize_agent_key(str(x)) for x in deps if str(x).strip()]
        sessions.append(sess)
    contract: dict[str, Any] = {}
    op = mission.get("output_paths") or []
    if op:
        contract["output_paths_hint"] = op[:20]
    if mission.get("heartbeat_recurring_requested"):
        contract["heartbeat_recurring_requested"] = True
    payload: dict[str, Any] = {
        "requested_by": uid,
        "goal": goal[:2000],
        "sessions": sessions,
        "timebox_minutes": int(mission.get("timebox_minutes") or 60),
        "approval_policy": {
            "mode": "plan_only",
            "allow_file_read": False,
            "allow_file_write": False,
            "allow_shell": False,
            "allow_network": False,
            "allow_git": False,
        },
    }
    if contract:
        payload["mission_contract"] = contract
    return payload


def try_record_initial_spawn_heartbeat(
    db: Session,
    *,
    user_id: str,
    spawn_group_id: str,
    recurring_requested: bool = False,
) -> str | None:
    """
    One boss heartbeat per spawn success (rate-limit aware — single call per spawn).
    """
    from app.services.agent_runtime.heartbeat import background_heartbeat

    uid = (user_id or "").strip()[:64]
    sg = (spawn_group_id or "").strip()
    msg = f"Initial heartbeat — bounded mission started (`{sg}`)."
    if recurring_requested:
        msg += " Recurring scheduling is not enabled on this host; recorded one-shot status only."
    try:
        background_heartbeat(
            db,
            user_id=uid,
            payload={
                "agent_handle": "boss",
                "assignment_id": None,
                "spawn_group_id": sg,
                "status": "running",
                "message": msg[:2000],
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("initial spawn heartbeat failed: %s", exc)
        return f"Spawn created; heartbeat could not be recorded: {exc!s}"[:500]
    lines = ["**Initial heartbeat recorded.**"]
    if recurring_requested:
        lines.append(
            "**Recurring** heartbeat scheduling is **not** enabled on this host yet — "
            "single status heartbeat only."
        )
    return "\n".join(lines)


def handle_runtime_tool_turn(
    db: Session,
    *,
    user_id: str,
    text: str,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Deterministic runtime path: valid bounded mission → sessions_spawn + initial heartbeat.
    Returns a structured dict for callers; None when this handler does not apply.
    """
    mission = detect_valid_bounded_mission(text)
    if mission is None:
        return None
    from app.services.agent_runtime.sessions import sessions_spawn

    uid = (user_id or "").strip()[:64]
    payload = mission_payload_for_spawn(user_id=uid, mission=mission)
    try:
        out = sessions_spawn(db, user_id=uid, payload=payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("handle_runtime_tool_turn sessions_spawn: %s", exc)
        return {
            "tool": "sessions_spawn",
            "ok": False,
            "error": str(exc)[:2000],
            "reply": f"Could not create mission: {exc!s}"[:2000],
        }
    sg = str(out.get("spawn_group_id") or "")
    hb_note = try_record_initial_spawn_heartbeat(
        db,
        user_id=uid,
        spawn_group_id=sg,
        recurring_requested=bool(mission.get("heartbeat_recurring_requested")),
    )
    reply = format_sessions_spawn_result(
        out,
        initial_heartbeat_note=hb_note,
    )
    return {
        "tool": "sessions_spawn",
        "ok": True,
        "spawn_group_id": sg,
        "reply": reply,
        "session_id": session_id,
    }

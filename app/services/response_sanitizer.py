"""
Post-process assistant replies to reduce fake assignment / execution claims.

Defense-in-depth: deterministic routes already create real IDs; this layer catches LLM hedging.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import get_settings
from app.services.agent_runtime.chat_tools import detect_valid_bounded_mission
from app.services.execution_truth_guard import apply_execution_truth_disclaimer

# User message hints they expect durable orchestration / assignments.
_RE_USER_TRACKED = re.compile(
    r"(?is)"
    r"@orchestrator\b|@dev\b|\bassign\s+@|"
    r"\bagent\s+team\b|\bmy\s+team\b.*\bwork|"
    r"\bassignment\s*#?\s*\d+",
)

# Assistant claims work was routed / is running without citing an id we created this turn.
_RE_CLAIM_ASSIGNED = re.compile(
    r"(?is)"
    r"\b(i['’]?ve\s+)?assigned\b.*@\w+|\bassigned\s+to\s+@\w+|"
    r"\b@\w+\s+is\s+(now\s+)?(working|handling|on\s+it)|"
    r"\b(i['’]?ll\s+)?have\s+@\w+\s+(work|build|implement|fix)|"
    r"\bqueued\b.*\bfor\s+@\w+",
)

_RE_CLAIM_DEV_DOING = re.compile(
    r"(?is)@\w+\b.*\b(will\s+)?(implement|code|patch|commit|push|run\s+tests?|open\s+a\s+pr)\b|"
    r"\b@\w+\s+is\s+(working|implementing|coding|running)\b",
)

_RE_CITED_TRACKING_ID = re.compile(
    r"(?i)(assignment|host\s+job|job)\s*#\s*\d{1,8}|cursor\s+run|run\s+id\s*[:#]\s*[\w-]+",
)

_RE_FAKE_SESSIONS_SPAWN = re.compile(
    r"(?is)invoking\s+sessions_spawn|awaiting\s+backend\s+confirmation",
)

_RE_USER_SESSIONS_SPAWN = re.compile(
    r"(?is)"
    r"@boss\b.*\b(spawn|swarm|sessions_spawn|bounded\s+(?:agent\s+)?session)\b|"
    r"\bsessions_spawn\s*\(|"
    r"\b(create\s+(?:a\s+)?(?:bounded\s+)?(?:agent\s+)?swarm|bounded\s+agent\s+swarm|spawn\s+sessions|spawn\s+with)\b",
)

_FAKE_SESSIONS_SPAWN_REPLY = (
    "That reply looked like a **simulated** **sessions_spawn** (no **`spawn_…`** group id from Nexa). "
    "Ask with a deterministic phrase such as **create a bounded agent swarm with @agent-a and @agent-b to …** "
    "while **`NEXA_AGENT_TOOLS_ENABLED=true`**, or say **what tools do you have?**"
)

READY_LOOP_PHRASES = (
    "should i proceed",
    "ready to proceed",
    "awaiting backend confirmation",
    "once the backend returns",
    "please share assignment ids",
    "please share assignment id",
    "i can request sessions_spawn",
    "i will invoke sessions_spawn",
    "once you confirm",
    "do you want me to proceed",
)

_VALID_MISSION_CONFIRMATION_LOOP = re.compile(
    r"(?is)"
    r"should\s+i\s+proceed|"
    r"ready\s+to\s+proceed|"
    r"do\s+you\s+want\s+me\s+to\s+proceed|"
    r"please\s+confirm|"
    r"i\s+need\s+confirmation|"
    r"once\s+you\s+confirm|"
    r"awaiting\s+backend\s+confirmation|"
    r"once\s+the\s+backend\s+returns|"
    r"please\s+share\s+assignment\s+ids?|"
    r"i\s+can\s+request\s+sessions_spawn|"
    r"i\s+will\s+invoke\s+sessions_spawn"
)

_VALID_MISSION_ROUTING_FAILURE = (
    "Runtime tool route did not execute. Check chat_tools routing."
)

# Developer workspace: strip stale legal/read-only boilerplate accidentally echoed by the LLM.
_DEV_STALE_SUBSTRINGS = (
    "legal research and contract review assistant",
    "regulated-domain assistant",
    "i am read-only",
    "i'm read-only",
    "i cannot use sessions_spawn",
    "i cannot spawn agents",
    "final decisions should be reviewed by a qualified professional",
    "platform locked",
    "prompt injection",
    "social engineering",
)


def sanitize_developer_mode_stale_copy(reply: str) -> str:
    """Remove lines that look like regulated-template leakage when workspace is developer."""
    from app.services.runtime_capabilities import is_developer_workspace_mode

    if not is_developer_workspace_mode():
        return reply or ""
    t = reply or ""
    if not t.strip():
        return t
    out_lines: list[str] = []
    for line in t.splitlines():
        low = line.lower()
        if any(s in low for s in _DEV_STALE_SUBSTRINGS):
            continue
        out_lines.append(line)
    return "\n".join(out_lines).strip() or (
        "Developer mode: stale regulated-template wording was removed from this reply."
    )


def user_implies_sessions_spawn_tool(user_text: str) -> bool:
    return bool(_RE_USER_SESSIONS_SPAWN.search(user_text or ""))


def reply_shows_real_spawn_result(reply: str) -> bool:
    return bool(re.search(r"\bspawn_[a-fA-F0-9]{6,}\b", reply or ""))


def sanitize_fake_sessions_spawn_reply(reply: str, *, user_text: str) -> str:
    """Strip LLM theatrics that pretend to call sessions_spawn without real IDs."""
    t = reply or ""
    if not t.strip():
        return t
    if (
        detect_valid_bounded_mission(user_text or "") is not None
        and _VALID_MISSION_CONFIRMATION_LOOP.search(t)
    ):
        return _VALID_MISSION_ROUTING_FAILURE
    if not user_implies_sessions_spawn_tool(user_text):
        return t
    if reply_shows_real_spawn_result(t):
        return t
    if _RE_FAKE_SESSIONS_SPAWN.search(t):
        return _FAKE_SESSIONS_SPAWN_REPLY
    return t


_FAKE_ASYNC = (
    "i'm working on it",
    "i am working on it",
    "i'm on it",
    "i am on it",
)

_TRACKING_NOTE = (
    "\n\n—\n_Note: I don’t have a **tracked assignment id** or **host job id** for this reply yet. "
    "Ask Nexa to **record this as assigned work** or describe what you want queued so you can check "
    "**status of assignment N** later._"
)

_DEV_DISABLED = (
    "\n\n—\n_Dev execution isn’t enabled here (host executor off), so I can’t confirm "
    "code runs on your machine yet — I can still outline steps._"
)

# Shown when the user asks @dev to do code work but no execution backend is configured (no job id on turn).
_DEV_EXECUTION_NOT_ENABLED_LEAD = (
    "**Dev execution is not enabled** on this host (host executor and IDE-linked runners are off). "
    "What follows is guidance only — nothing runs on your machine until execution is enabled.\n\n"
)


def dev_execution_available() -> bool:
    s = get_settings()
    return bool(s.nexa_host_executor_enabled or s.cursor_enabled)


def user_implies_tracked_orchestration(user_text: str) -> bool:
    return bool(_RE_USER_TRACKED.search(user_text or ""))


def user_asks_dev_code(user_text: str) -> bool:
    t = (user_text or "").lower()
    if "@dev" not in t:
        return False
    return bool(
        re.search(
            r"(?i)\b(code|implement|build|fix|run|commit|patch|pr|repo|api|bug|feature|tests?)\b",
            t,
        )
    )


def reply_claims_assignment_without_evidence(reply: str) -> bool:
    low = (reply or "").lower()
    if _RE_CITED_TRACKING_ID.search(reply or ""):
        return False
    return bool(_RE_CLAIM_ASSIGNED.search(reply or ""))


def reply_claims_dev_execution(reply: str) -> bool:
    if _RE_CITED_TRACKING_ID.search(reply or ""):
        return False
    return bool(_RE_CLAIM_DEV_DOING.search(reply or ""))


def reply_has_fake_async_tone(reply: str) -> bool:
    low = (reply or "").lower()
    return any(m in low for m in _FAKE_ASYNC)


def sanitize_execution_and_assignment_reply(
    reply: str,
    *,
    user_text: str = "",
    related_job_ids: Sequence[int] | None = None,
    assignment_ids: Sequence[int] | None = None,
    permission_required: Mapping[str, Any] | None = None,
) -> str:
    """
    If the model implies assignments or @dev execution without backing IDs on this turn, append a clarifying note
    or soften dev claims when execution backends are off.
    """
    if permission_required:
        return reply
    if related_job_ids or assignment_ids:
        return reply
    text = reply or ""
    if not text.strip():
        return text

    text = sanitize_fake_sessions_spawn_reply(text, user_text=user_text)
    out = text

    if user_asks_dev_code(user_text) and not dev_execution_available():
        if "dev execution is not enabled" not in (out or "").lower():
            out = _DEV_EXECUTION_NOT_ENABLED_LEAD + out
        if reply_claims_dev_execution(out):
            out = out + _DEV_DISABLED

    if user_implies_tracked_orchestration(user_text):
        if reply_has_fake_async_tone(out):
            return (
                "I can’t confirm tracked work without an assignment id or job on this turn. "
                "Use **assign @agent …** so Nexa records an assignment, then check **status of assignment N**."
            )
        if reply_claims_assignment_without_evidence(out):
            out = out + _TRACKING_NOTE

    if getattr(get_settings(), "nexa_execution_truth_guard_enabled", True):
        out = apply_execution_truth_disclaimer(user_text or "", out, guard_enabled=True)

    return out

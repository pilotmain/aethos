"""Deterministic V1 planner — keyword routing to agent handles (no LLM)."""

from __future__ import annotations

import re
from typing import Any

DEFAULT_ORCHESTRATOR = "orchestrator"

# Topic / market / industry research — not local filesystem work (Rule 1).
_TOPIC_MARKET_PHRASES: tuple[str, ...] = (
    "summarize this market",
    "analyze this market",
    "research this market",
    "market analysis",
    "this market:",
    "research the market",
    "competitors in",
    "competitor analysis",
    "industry analysis",
    "research this topic",
    "the market for",
    "market for ",
    "market overview",
    "summarize the market",
)


def _explicit_local_filesystem_intent(low: str) -> bool:
    """Only treat as path/folder work when the user clearly asks for local files (Rule 2)."""
    if any(
        p in low
        for p in (
            "folder",
            "directory",
            "local file",
            "local folder",
            "read file",
            "read folder",
            "analyze folder",
            "list files in",
            "list files",
            "files in ",
            "open folder",
        )
    ):
        return True
    # Relative / home / obvious unix paths in the message
    if re.search(r"(?:^|\s)(~/|\./|\.\./)", low):
        return True
    if re.search(r"(?:/users/|/home/|/tmp/|/var/folders/)", low, re.I):
        return True
    return False


def topic_market_assignment_intent(text: str) -> bool:
    """True when the instruction is market/topic research, not local disk analysis."""
    low = (text or "").lower().strip()
    if not low:
        return False
    if _explicit_local_filesystem_intent(low):
        return False
    if any(p in low for p in _TOPIC_MARKET_PHRASES):
        return True
    if ("market" in low or "industry" in low) and any(
        k in low for k in ("summarize", "analyze", "research", "overview")
    ):
        return True
    if "research" in low and any(k in low for k in ("competitor", "competition", "topic")):
        return True
    return False


def assignment_skips_host_path_inference(text: str) -> bool:
    """
    When True, skip host_executor / local_file prechecks for this assignment text.

    Market and topic prompts must not produce folder clarification or /app/... synthetic paths.
    """
    low = (text or "").lower().strip()
    if not low:
        return True
    if _explicit_local_filesystem_intent(low):
        return False
    return topic_market_assignment_intent(low)


_RE_DEV = re.compile(
    r"(?i)\b(refactor|implement|bug\s*fix|bugfix|fix\s+the\s+bug|unit\s+tests?|add\s+tests?|"
    r"migrate|endpoint|pull\s+request|\bpr\b|open\s+a\s+pr|create\s+a\s+pr|codebase|"
    r"lint\s+errors?|typescript\s+migration|ci\s+(?:fix|pipeline))\b"
)


def development_assignment_intent(text: str) -> bool:
    """Coding / repo work suitable for Cursor Cloud or dev agents (not market research)."""
    low = (text or "").lower().strip()
    if not low:
        return False
    if topic_market_assignment_intent(low):
        return False
    if _explicit_local_filesystem_intent(low):
        return False
    if _RE_DEV.search(low):
        return True
    if any(p in low for p in ("write code", "change code", "patch the", "add feature")):
        return True
    return False


def classify_assignment_instruction_kind(text: str) -> str:
    """Return ``market_analysis`` | ``file_folder`` | ``development`` | ``general_assignment``."""
    low = (text or "").lower().strip()
    if not low:
        return "general_assignment"
    if _explicit_local_filesystem_intent(low):
        return "file_folder"
    if topic_market_assignment_intent(low):
        return "market_analysis"
    if development_assignment_intent(text or ""):
        return "development"
    return "general_assignment"


def extract_topic_from_instruction(text: str) -> str:
    """Prefer text after the first colon for ``summarize this market: …`` style prompts."""
    t = (text or "").strip()
    if ":" in t:
        rest = t.split(":", 1)[1].strip()
        if rest:
            return rest[:4000]
    return t[:4000]


def build_assignment_input_json(instr: str, *, kind: str | None = None) -> dict[str, Any]:
    """Structured ``input_json`` for AgentAssignment (Mission Control + dispatch guards)."""
    k = kind or classify_assignment_instruction_kind(instr)
    out: dict[str, Any] = {
        "user_message": instr[:4000],
        "source": "chat",
        "kind": k,
    }
    if k == "development":
        out["task_type"] = "development"
    if k == "market_analysis":
        out["topic"] = extract_topic_from_instruction(instr)
    return out


def plan_tasks_from_goal(goal: str) -> list[dict[str, Any]]:
    """
    Return a list of {assigned_to, title, description} dicts for one user goal.

    Uses simple keyword buckets; falls back to a single orchestrator clarification slot
    when no keyword matches (caller should ask user to name agents).
    """
    g = (goal or "").strip()
    if not g:
        return []

    low = g.lower()
    out: list[dict[str, Any]] = []

    # Legal / contract
    if any(k in low for k in ("contract", "legal", "risk", "liability", "terms of service")):
        out.append(
            {
                "assigned_to": "legal-reviewer",
                "title": "Contract / legal review",
                "description": g[:4000],
                "input_json": {
                    "user_message": g[:4000],
                    "goal": g[:4000],
                    "source": "chat",
                    "kind": "general_assignment",
                },
            }
        )

    # Sales / email (avoid bare "customer" — it appears in "customer support" market research)
    if any(k in low for k in ("email", "follow-up", "follow up", "proposal", "crm", "outbound")):
        out.append(
            {
                "assigned_to": "sales-followup",
                "title": "Customer follow-up",
                "description": g[:4000],
                "input_json": {
                    "user_message": g[:4000],
                    "goal": g[:4000],
                    "source": "chat",
                    "kind": "general_assignment",
                },
            }
        )

    # Research / market / summarize — structured topic/market rows when applicable
    if any(k in low for k in ("research", "market", "summarize", "competitor", "industry")):
        ra_ij = build_assignment_input_json(g[:4000])
        ra_ij["goal"] = g[:4000]
        title_ra = "Market analysis" if ra_ij.get("kind") == "market_analysis" else "Research & summarize"
        out.append(
            {
                "assigned_to": "research-analyst",
                "title": title_ra,
                "description": g[:4000],
                "input_json": ra_ij,
            }
        )

    # Dedupe by assigned_to keeping order
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in out:
        h = str(item.get("assigned_to") or "").lower()
        if h and h not in seen:
            seen.add(h)
            deduped.append(item)

    if deduped:
        return deduped

    # Unclear — orchestrator asks for clarification (no fake agent execution)
    return [
        {
            "assigned_to": DEFAULT_ORCHESTRATOR,
            "title": "Clarify goal",
            "description": g[:4000],
            "input_json": {
                "user_message": g[:4000],
                "goal": g[:4000],
                "source": "chat",
                "kind": "general_assignment",
            },
        }
    ]


_RE_ASSIGN = re.compile(
    r"(?is)^\s*assign\s+@([\w-]{1,64})\s+to\s+(.+?)\s*$"
)
_RE_ASSIGN_ALT = re.compile(
    r"(?is)^\s*assign\s+@([\w-]{1,64})\s+(.+)$"
)


def parse_explicit_assign(text: str) -> tuple[str, str] | None:
    """Return (handle, instruction) for explicit `assign @handle to ...` lines."""
    t = (text or "").strip()
    m = _RE_ASSIGN.match(t)
    if m:
        return (m.group(1).strip().lower(), (m.group(2) or "").strip())
    m2 = _RE_ASSIGN_ALT.match(t)
    if m2:
        return (m2.group(1).strip().lower(), (m2.group(2) or "").strip())
    return None

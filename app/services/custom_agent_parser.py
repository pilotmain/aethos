"""
Deterministic parse: natural language → custom agent spec (no LLM).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def _norm_handle_key(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").lower()).strip("_")


def is_operator_runtime_handle(handle: str) -> bool:
    """
    Handles that should default to Base Operator in developer workspaces — not legal templates.
    Matches chief-operator, orchestrator, runtime-focused agents, etc.
    """
    n = _norm_handle_key(handle)
    if not n:
        return False
    needles = (
        "chief_operator",
        "chiefoperator",
        "boss",
        "executor",
        "orchestrator",
        "researcher",
        "analyst",
        "developer",
        "mission",
        "runtime",
        "operator",
        "swarm",
        "_qa",
        "qa_",
    )
    return any(x in n for x in needles)


def explicit_regulated_domain_request(text: str) -> bool:
    """Strong signals for legal/medical/tax/compliance agents — used in developer workspaces."""
    tl = (text or "").lower()
    phrases = (
        "lawyer",
        "attorney",
        "legal advice",
        "legal counsel",
        "contract review",
        "review contracts",
        "review contract",
        "legal research",
        "litigation",
        "lawsuit",
        "tax advice",
        "tax filing",
        "cpa ",
        "medical advice",
        "diagnosis",
        "physician",
        "doctor ",
        "compliance officer",
        "hipaa",
        "fiduciary",
        "regulated domain",
        "investment advice",
        "tax preparer",
        "binding advice",
    )
    if any(p in tl for p in phrases):
        return True
    if re.search(r"(?i)\blegal\b", tl):
        return True
    return False


# Terms that imply regulated-domain assistance (safety_level = regulated)
_REGULATED_HINTS = (
    "lawyer",
    "attorney",
    "legal",
    "contract",
    "lawsuit",
    "medical",
    "doctor",
    "diagnosis",
    "treat",
    "cpa",
    "tax filing",
    "tax advice",
    "investment advice",
    "insurance",
    "compliance",
    "fiduciary",
)

_GUARD_TOKENS = (
    "human review",
    "qualified professional",
    "licensed",
    "not final",
    "not a lawyer",
    "not an attorney",
    "before final",
)


@dataclass
class ParsedCustomAgent:
    handle: str
    display_name: str
    role: str
    description: str
    skills: list[str] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
    safety_level: str = "standard"
    knowledge_scope: str | None = None


def _title_case_handle(h: str) -> str:
    t = re.sub(r"[-_]+", " ", (h or "").strip())
    return " ".join(w[:1].upper() + w[1:] if w else w for w in t.split()) or h


def infer_regulated(text: str) -> bool:
    tl = (text or "").lower()
    return any(x in tl for x in _REGULATED_HINTS)


_BAD_HANDLE_SUBSTRINGS = (
    "can_you",
    "could_you",
    "please_create",
    "create_multi",
    "can_you_create",
    "multi_agents_that",
)

# Normalized tokens — never treat section labels / prose as agent handles.
_STOP_HANDLE_WORDS = frozenset(
    {
        "role",
        "skills",
        "guardrails",
        "use_it_by_saying",
        "behavior_rules",
        "execution_rules",
        "visual_formatting",
        "mission",
        "status",
        "title",
        "progress",
        "heartbeat",
    }
)


def is_valid_user_agent_handle(handle: str) -> bool:
    """
    Reject sentence-derived or absurd handles; prefer explicit short slugs from the user.

    Rules: 3–40 chars, ``[a-zA-Z0-9_-]``, at most five hyphen/underscore segments, no obvious
    question-derived prefixes.
    """
    h = (handle or "").strip().lstrip("@")
    if not h:
        return False
    hl = h.lower()
    if len(hl) < 3 or len(hl) > 40:
        return False
    if not re.match(r"^[a-zA-Z0-9_-]+$", hl):
        return False
    parts = [p for p in re.split(r"[-_]+", hl) if p]
    if len(parts) > 5:
        return False
    if len(parts) >= 2 and parts[0] == "can" and parts[1] in ("you", "u"):
        return False
    joined = "_".join(parts)
    for bad in _BAD_HANDLE_SUBSTRINGS:
        if bad in joined:
            return False
    for seg in parts:
        sl = seg.lower()
        if sl in _STOP_HANDLE_WORDS:
            return False
        for w in _STOP_HANDLE_WORDS:
            if sl.startswith(w + "_") or sl.endswith("_" + w):
                return False
    return True


def extract_explicit_agent_creation_handles(text: str) -> list[str] | None:
    """
    Pattern C: ``Create these agents:`` followed by lines that are only ``@handle``.

    Returns None when this block pattern is not present.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    if not re.match(r"(?is)^create\s+these\s+agents\s*:?\s*$", raw.split("\n", 1)[0].strip()):
        return None
    lines = raw.split("\n")[1:]
    handles: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^@([\w-]{2,64})\s*$", s)
        if not m:
            return None
        hk = m.group(1).strip().lower()
        if not is_valid_user_agent_handle(hk):
            continue
        nk = re.sub(r"[^a-z0-9]+", "_", hk).strip("_")
        if nk in _STOP_HANDLE_WORDS:
            continue
        if hk not in handles:
            handles.append(hk)
    return handles if handles else None


def _looks_like_post_creation_spec_sheet(text: str) -> bool:
    """Feedback like 'Created custom agent …' plus Role:/Skills: — not a new create request."""
    t = (text or "").strip()
    if not t:
        return False
    if re.match(r"(?is)^created\s+custom\s+agent\s+@", t):
        return True
    first = t.split("\n", 1)[0].strip().lower()
    if "create" in first or "make " in first or "add " in first:
        return False
    if re.search(r"(?im)^\s*role\s*:", t) and re.search(r"(?im)^\s*skills\s*:", t):
        return True
    return False


def _split_skills_guards(chunk: str) -> tuple[list[str], list[str]]:
    """Split a trailing clause into skills vs guardrails heuristics."""
    skills: list[str] = []
    guards: list[str] = []
    parts = re.split(r",|\band\b|;", chunk)
    for p in parts:
        s = (p or "").strip()
        if not s or len(s) > 400:
            continue
        sl = s.lower()
        if any(g in sl for g in _GUARD_TOKENS) or "final decision" in sl or "not provide" in sl:
            guards.append(s.rstrip(".,;"))
        else:
            skills.append(s.rstrip(".,;"))
    return skills, guards


def parse_custom_agent_from_prompt(text: str) -> ParsedCustomAgent | None:
    """
    Parse 'Create me a custom agent called @x. It should ...' style prompts.
    Returns None if no @handle found (caller may use other creation paths).
    """
    raw = (text or "").strip()
    if not raw:
        return None
    if _looks_like_post_creation_spec_sheet(raw):
        return None
    m_at = re.search(r"@([\w][\w-]{0,62})\b", raw)
    if not m_at:
        m_cal = re.search(
            r"(?is)agent\s+(?:called|named)\s+['\"]?([^\n'\"@.]+)['\"]?", raw
        )
        if m_cal:
            h = re.sub(r"[^a-zA-Z0-9\-_]+", "-", m_cal.group(1).strip())[:64].strip("-")
        else:
            return None
    else:
        h = m_at.group(1).strip().lower()
    if not h:
        return None
    if not is_valid_user_agent_handle(h):
        return None

    display = _title_case_handle(h)
    body_low = raw.lower()

    role = f"{display} — custom Nexa assistant"
    skills: list[str] = []
    guards: list[str] = []

    m_should = re.search(r"(?is)\bit\s+should\s+(.+?)(?:\.(?:\s+|$)|$)", raw)
    if m_should:
        chunk = m_should.group(1).strip()
        skills, guards = _split_skills_guards(chunk)
    else:
        # skills after em-dash or colon on same line as handle
        m_tail = re.search(r"(?:—|:)\s*(.+)$", raw.split("\n", 1)[0])
        if m_tail:
            skills, g2 = _split_skills_guards(m_tail.group(1))
            guards.extend(g2)

    from app.core.config import get_settings

    s = get_settings()
    developer_templates = (s.nexa_workspace_mode or "").strip().lower() == "developer"

    if developer_templates:
        regulated = explicit_regulated_domain_request(raw)
    else:
        regulated = infer_regulated(raw)

    if regulated:
        if not any("human" in (x or "").lower() or "review" in (x or "").lower() for x in guards):
            guards.append("Requires human review before final decisions")
        guards.append(
            "Does not provide final legal, medical, or tax advice; research and drafting support only"
        )

    # de-dup
    def _dedupe(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in seq:
            k = (x or "").strip().lower()
            if k and k not in seen:
                seen.add(k)
                out.append((x or "").strip())
        return out

    skills = _dedupe(skills)[:20]
    guards = _dedupe(guards)[:20]

    if regulated:
        sl = "regulated"
        role = (
            "Legal research and contract review assistant"
            if "contract" in body_low or "legal" in body_low
            else f"{display} (regulated-domain assistant)"
        )
    else:
        sl = "standard"
        if developer_templates:
            role = "Base Operator / System Orchestrator"
            if not skills:
                skills = [
                    "Runtime tool coordination",
                    "sessions_spawn",
                    "background_heartbeat",
                    "Mission Control reporting",
                    "Assignment tracking",
                ]
            if not guards:
                guards = [
                    "Uses only registered runtime tools",
                    "Does not claim execution without backend confirmation",
                    "Bounded missions only",
                ]
        else:
            role = f"{display} — custom Nexa assistant"

    desc = (
        f"Reviews and assists with: {', '.join(skills[:5])}."
        if skills
        else f"Custom agent {display} — follow system instructions for scope."
    )[:2000]

    return ParsedCustomAgent(
        handle=h,
        display_name=display,
        role=role,
        description=desc,
        skills=skills,
        guardrails=guards,
        safety_level=sl,
    )

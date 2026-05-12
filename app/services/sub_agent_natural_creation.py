# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Natural-language creation of orchestration sub-agents (registry), distinct from LLM custom agents.

Priority is enforced in :mod:`app.services.intent_classifier` and Telegram/web pipelines.
"""

from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.agent.activity_tracker import get_activity_tracker
from app.services.sub_agent_registry import AgentRegistry


def normalize_sub_agent_domain(raw: str) -> str:
    """Map user words to registry/executor domain keys (distinct from :func:`~app.services.team.roles.normalize_role_key`)."""
    k = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not k:
        return "general"
    aliases = {
        "github": "git",
        "gh": "git",
        "quality": "qa",
        "quality_assurance": "qa",
        "pytest": "test",
        "sec": "security",
        "deploy": "vercel",
        "infrastructure": "ops",
        "infra": "ops",
        "operations": "ops",
        "platform": "ops",
        "rail": "railway",
    }
    k = aliases.get(k, k)
    known = frozenset(
        {
            "git",
            "vercel",
            "railway",
            "ops",
            "qa",
            "test",
            "security",
            "marketing",
            "ceo",
            "support",
            "scrum",
            "backend",
            "frontend",
            "design",
            "general",
        }
    )
    return k if k in known else "general"


# Longest keys first — substring hits must prefer specific roles (Phase 54).
_NAME_DOMAIN_FRAGMENTS: tuple[tuple[str, str], ...] = (
    ("product_manager_agent", "general"),
    ("designer_agent", "design"),
    ("backend_agent", "backend"),
    ("frontend_agent", "frontend"),
    ("product_manager", "general"),
    ("designer", "design"),
    ("marketing_agent", "marketing"),
    ("security_agent", "security"),
    ("qa_agent", "qa"),
)


_CREATION_VERBS = re.compile(r"(?i)\b(create|make|add|build|spawn)\b")
_EXTENDED_CREATION_VERBS = re.compile(
    r"(?i)\b(create|make|add|build|spawn|set\s+up|generate)\b"
)
_VOLITION_SPAWN = re.compile(r"(?i)\b(i\s+need|i\s+want|give\s+me|get\s+me)\b")
_CREATION_TEAM_WORDS = re.compile(
    r"(?i)\b(agents?|sub[- ]?agents?|subagents?|assistants?|teammates?|workers?|bots?)\b"
)

# Polite / conversational spawn requests (Phase NL — include question forms).
_RE_EXPLICIT_CONVERSATIONAL_SPAWN = re.compile(
    r"(?is)\b(?:can|could|would)\s+you\s+(?:please\s+)?(?:create|make|spawn|add|set\s+up|build)\s+"
    r"(?:an?\s+)?(?:a\s+)?[^\n]{0,160}?\b(agent|specialist|expert|assistant)\s*\??"
)
_RE_VOLITION_SPAWN_TAIL = re.compile(
    r"(?is)^\s*(?:i\s+need|i\s+want|give\s+me|get\s+me)\s+(?:an?\s+)?(?:a\s+)?[^\n]{1,120}\b(agent|specialist|expert|assistant)\b"
)
_RE_SETUP_SPAWN = re.compile(
    r"(?is)^\s*(?:create|make|spawn|add|build|set\s+up|generate)\s+(?:me\s+)?(?:an?\s+)?(?:a\s+)?[^\n]{1,120}\b(agent|specialist|expert|assistant)\b"
)


def _nl_explicit_conversational_spawn_line(text: str) -> bool:
    """Single-agent spawn cues including 'Can you create … agent?' and 'I need a QA specialist'."""
    raw = (text or "").strip()
    if not raw:
        return False
    if _RE_EXPLICIT_CONVERSATIONAL_SPAWN.search(raw):
        return True
    if _RE_VOLITION_SPAWN_TAIL.search(raw):
        return True
    if _RE_SETUP_SPAWN.search(raw):
        return True
    return False


def looks_like_registry_agent_creation_nl(text: str) -> bool:
    """
    True → user is issuing an imperative **orchestration roster** command (sub-agents), not a
    vague multi-agent *capability* question.

    Matches ``create … agents / assistants / *_agent``, etc., so NL never falls through to
    LLM-only custom agents when the user meant Mission Control sub-agents.
    """
    raw = (text or "").strip()
    if not raw:
        return False
    from app.services.multi_agent_routing import is_multi_agent_capability_question

    # Conversational spawn ("Can you create a marketing agent?", "I need a QA specialist").
    if _nl_explicit_conversational_spawn_line(raw) and not is_multi_agent_capability_question(raw):
        return True

    has_creation_verb = bool(_EXTENDED_CREATION_VERBS.search(raw) or _VOLITION_SPAWN.search(raw))
    if not has_creation_verb:
        return False

    if is_multi_agent_capability_question(raw):
        return False
    tl = raw.lower()
    # Question-shaped — allow explicit conversational spawn (handled above); block vague tutorials.
    if "?" in raw and not _nl_explicit_conversational_spawn_line(raw):
        return False
    first_w = tl.split()[0] if tl.split() else ""
    if first_w in (
        "can",
        "could",
        "how",
        "what",
        "why",
        "would",
        "is",
        "are",
        "do",
        "does",
        "did",
        "should",
        "will",
        "when",
        "where",
    ):
        # Allow "Can/Could/Would you create …" (already handled by conversational spawn).
        if not _RE_EXPLICIT_CONVERSATIONAL_SPAWN.search(raw):
            return False

    # Phase 59 — explicit roster NL (comma lists, "N agents:", numbered *_agent lines) → sub-agent registry.
    if (
        re.search(
            r"(?is)\b(?:create|make|add|build|spawn)\s+(?:these\s+)?(?:two|three|four|five|six|seven|eight|nine|ten|\d+)\s+agents?\s*[,:]",
            raw,
        )
        or (
            _CREATION_VERBS.search(raw)
            and re.search(r"(?im)^\s*\d+[\).]\s*.+_agent\b", raw)
        )
        or re.search(
            r"(?i)\b(?:create|make|add|build|spawn)\s+(?:[a-z0-9][a-z0-9_-]{0,62}_agent\s*,\s*)+[a-z0-9][a-z0-9_-]{0,62}_agent\b",
            raw,
        )
        or re.search(
            r"(?i)\b(?:create|make|add|build|spawn)\s+[a-z0-9][a-z0-9_-]{0,62}_agent\s+and\s+[a-z0-9][a-z0-9_-]{0,62}_agent\b",
            raw,
        )
    ):
        return True

    if _CREATION_TEAM_WORDS.search(raw):
        return True
    if "agent" in tl:
        return True
    if re.search(r"(?i)\b[a-z0-9][a-z0-9_-]{0,62}_agent\b", raw):
        return True
    return False


def prefers_registry_sub_agent(text: str) -> bool:
    """
    True → route to orchestration sub-agent registry (Phase 48 / 53).

    Alias for :func:`looks_like_registry_agent_creation_nl` (backward-compatible name).
    """
    return looks_like_registry_agent_creation_nl(text)


def _infer_domain(name: str, full_text: str) -> str:
    """Pick registry domain from handle + message (Phase 47 / 54 — never guess **qa** without cues)."""
    n = (name or "").lower()
    ctx = (full_text or "").lower()
    blob = f"{n} {ctx}"

    for frag, dom in sorted(_NAME_DOMAIN_FRAGMENTS, key=lambda x: -len(x[0])):
        if frag in n:
            return normalize_sub_agent_domain(dom)

    # Name-first (handles like qa_agent, marketing_agent)
    if n.endswith("_agent"):
        prefix = n[: -len("_agent")]
        if prefix in (
            "qa",
            "marketing",
            "security",
            "ops",
            "ceo",
            "support",
            "scrum",
            "test",
            "git",
            "vercel",
            "railway",
            "backend",
            "frontend",
            "design",
            "product_manager",
            "designer",
        ):
            if prefix == "product_manager":
                return "general"
            if prefix == "designer":
                return normalize_sub_agent_domain("design")
            return prefix if prefix != "test" else "test"
    if n in ("qa", "qa_agent") or n.startswith("qa_"):
        return "qa"
    if "marketing" in n or n.startswith("market"):
        return "marketing"
    if "security" in n or n.startswith("sec_"):
        return "security"

    # Role phrases (design / product before generic QA heuristics)
    if re.search(r"\b(ui/ux|ux\s+design|user\s+interface\s+design|figma|mockups?)\b", blob):
        return normalize_sub_agent_domain("design")
    if re.search(r"\b(product\s+strategy|product\s+manager|roadmap|prd)\b", blob):
        return "general"

    if re.search(r"\bqa\b", blob) or "quality assurance" in blob or "quality_assurance" in blob:
        return "qa"
    if any(x in blob for x in ("marketing", "campaign", "copy", "brand")):
        return "marketing"
    if any(x in blob for x in ("security", "sec", "vuln")) and "qa" not in n:
        return "security"
    if any(x in blob for x in ("pytest", "lint", "integration test", "unit test")) and "qa" not in blob:
        return "test"
    if any(x in blob for x in ("ceo", "strategy", "exec")):
        return "ceo"
    if any(x in blob for x in ("support", "customer", "helpdesk")):
        return "support"
    if any(x in blob for x in ("scrum", "sprint", "agile")):
        return "scrum"
    if any(x in blob for x in ("ops", "railway", "infra", "deploy health")):
        return "ops"
    if "railway" in blob:
        return "railway"
    if any(x in blob for x in ("vercel", "preview deploy")):
        return "vercel"
    if any(x in blob for x in ("git", "github", "commit", "branch")):
        return "git"

    # Phase 49 — role phrases without strict handle prefixes
    if any(p in ctx for p in ("api development", "rest api", "graphql")) and "security" not in n:
        return "backend"
    if any(p in ctx for p in ("user interface", "react ", "next.js", "nextjs")):
        return "frontend"

    return normalize_sub_agent_domain(n.split("_")[0] if "_" in n else n)


def _clean_agent_chunk(chunk: str) -> str | None:
    c = chunk.strip().strip(".,;:")
    c = re.sub(r"(?i)\s+for\s+.+$", "", c).strip()
    c = re.sub(r"^[@/]+", "", c)
    if c and re.match(r"^[\w-]+$", c):
        return c[:64]
    return None


def _dedupe_specs(specs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for nm, dom in specs:
        key = nm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((nm, dom))
    return out


def _extract_role_based_agent_specs(text: str) -> list[tuple[str, str]]:
    """
    Match phrases like ``backend_agent for API development, frontend_agent for UI``.

    Each ``*_agent for <role>`` segment yields one spawn spec.
    """
    raw = (text or "").strip()
    if not raw:
        return []
    out: list[tuple[str, str]] = []
    for m in re.finditer(r"(?i)\b([a-z0-9][a-z0-9_]{0,62}_agent)\s+for\s+([^,\n]+)", raw):
        name = m.group(1).strip()
        role = (m.group(2) or "").strip()
        out.append((name, _infer_domain(name, f"{raw} {role}")))
    return out


def _split_agent_phrase_tail(segment: str) -> list[str]:
    """Split 'a, b and c' into name tokens."""
    s = segment.strip()
    if not s:
        return []
    chunks = re.split(r"\s+(?:,|and|&|;)\s*|\s*,\s*", s)
    out: list[str] = []
    for c in chunks:
        nm = _clean_agent_chunk(c)
        if nm:
            out.append(nm)
    return out


def _slugify_roster_title(title: str) -> str:
    """Turn a free-form roster line (e.g. financial advisor) into a handle-like id."""
    t = (title or "").strip().lstrip("@")
    if not t:
        return ""
    if re.match(r"^[\w-]+$", t) and len(t) <= 64:
        return t.lower()
    s = re.sub(r"[^\w\s\-]", "", t.lower())
    s = re.sub(r"[\s\-]+", "_", s.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:64] if s else "")


def _extract_numbered_agent_specs(segment: str, full_text: str) -> list[tuple[str, str]]:
    """Parse ``1. foo bar`` / ``2) @handle`` lines under a ``create … agents`` header."""
    specs: list[tuple[str, str]] = []
    for m in re.finditer(r"(?m)^\s*\d+[\).]\s*(.+)$", segment):
        title = (m.group(1) or "").strip()
        title = re.split(r"\s+[—\-]\s+|,\s+for\s+", title)[0].strip()
        slug = _slugify_roster_title(title)
        if slug:
            specs.append((slug, _infer_domain(slug, full_text)))
    return specs


def _parse_conversational_agent_specs(text: str) -> list[tuple[str, str]]:
    """
    Free-form single-agent lines: \"Create a marketing agent\", \"Can you create a QA agent?\",
    \"I need a QA specialist\".
    """
    raw = (text or "").strip()
    if not raw:
        return []
    rc = raw.rstrip("?!.")

    # Can/Could/Would you … create … agent / specialist / …
    m = re.search(
        r"(?is)\b(?:can|could|would)\s+you\s+(?:please\s+)?(?:create|make|spawn|add|set\s+up|build)\s+"
        r"(?:an?\s+)?(?:a\s+)?(.+?)\s+(agent|specialist|expert|assistant)(?:\s+.*)?$",
        rc,
    )
    if m:
        phrase = (m.group(1) or "").strip()
        phrase = re.sub(r"(?i)^a\s+", "", phrase)
        role = (m.group(2) or "agent").lower()
        if role == "agent":
            base = f"{phrase}_agent" if not phrase.endswith("_agent") else phrase
        else:
            base = f"{phrase}_{role}" if not phrase.endswith(f"_{role}") else phrase
        nm = _slugify_roster_title(base) or _slugify_roster_title(phrase)
        if nm:
            return [(nm, _infer_domain(nm, raw))]

    # I need / I want / Give me … agent|specialist|…
    m = re.match(
        r"(?is)^\s*(?:i\s+need|i\s+want|give\s+me|get\s+me)\s+(?:an?\s+)?(?:a\s+)?(.+?)\s+(agent|specialist|expert|assistant)(?:\s+.*)?$",
        rc,
    )
    if m:
        phrase = (m.group(1) or "").strip()
        phrase = re.sub(r"(?i)^a\s+", "", phrase)
        role = (m.group(2) or "agent").lower()
        if role == "agent":
            base = f"{phrase}_agent" if not phrase.endswith("_agent") else phrase
        else:
            base = f"{phrase}_{role}"
        nm = _slugify_roster_title(base) or _slugify_roster_title(phrase)
        if nm:
            return [(nm, _infer_domain(nm, raw))]

    # Create/Make/Spawn a … agent (optional tail: "… agent for product launch")
    m = re.match(
        r"(?is)^\s*(?:create|make|spawn|add|build|set\s+up|generate)\s+(?:me\s+)?(?:an?\s+)?(?:a\s+)?(.+?)\s+(agent|specialist|expert|assistant)\b(?:\s+.*)?$",
        rc,
    )
    if m:
        phrase = (m.group(1) or "").strip()
        role = (m.group(2) or "agent").lower()
        if role == "agent":
            base = f"{phrase}_agent" if not phrase.endswith("_agent") else phrase
        else:
            base = f"{phrase}_{role}"
        nm = _slugify_roster_title(base) or _slugify_roster_title(phrase)
        if nm:
            return [(nm, _infer_domain(nm, raw))]

    return []


def parse_natural_sub_agent_specs(text: str) -> list[tuple[str, str]]:
    """Return (name, domain) pairs to spawn."""
    raw = (text or "").strip()
    if not raw:
        return []

    conv = _parse_conversational_agent_specs(raw)
    if conv:
        return _dedupe_specs(conv)

    role_specs = _extract_role_based_agent_specs(raw)
    if role_specs:
        return _dedupe_specs(role_specs)

    # Plain-text CLI mimic (optional leading slash)
    m_cli = re.match(
        r"(?is)^\s*/?subagent\s+create\s+([^\s]+)\s+([^\s]+)\s*$",
        raw,
    )
    if m_cli:
        name = m_cli.group(1).strip().lstrip("@")
        dom = normalize_sub_agent_domain(m_cli.group(2))
        return [(name, dom)]

    # "create agent NAME DOMAIN" / "make agent NAME DOMAIN"
    m_pair = re.match(
        r"(?is)^\s*(?:create|make|add|build|spawn)\s+(?:an?\s+)?agent\s+"
        r"([^\s]+)\s+([^\s]+)\s*$",
        raw,
    )
    if m_pair:
        name = m_pair.group(1).strip().lstrip("@/")
        dom = normalize_sub_agent_domain(m_pair.group(2))
        return [(name, dom)]

    tl = raw.lower()
    specs: list[tuple[str, str]] = []

    # Multi: create [two] agents … / create agents …
    # Plural ``agents`` only (avoid matching ``create me an agent …`` single-create lines).
    multi_m = re.search(
        r"(?is)\b(?:create|make|add|build|spawn)\s+"
        r"(?:me\s+)?"
        r"(?:(?:two|three|several|four|five|\d+)\s+)?agents\s*(?:[:,]?\s*)",
        raw,
    )
    if multi_m:
        tail = raw[multi_m.end() :].strip()
        numbered = _extract_numbered_agent_specs(tail, raw)
        if numbered:
            return _dedupe_specs(numbered)
        names = _split_agent_phrase_tail(tail)
        for nm in names:
            specs.append((nm, _infer_domain(nm, raw)))
        if specs:
            return specs

    # Names that look like orchestration handles: qa_agent, /marketing_agent
    for m in re.finditer(r"(?i)(?:^|[\s,])(?:@|/)?([\w-]+_agent)\b", raw):
        nm = m.group(1).strip().lstrip("@/")
        specs.append((nm, _infer_domain(nm, raw)))

    # "called|named @handle" — single
    m_cn = re.search(
        r"(?is)\b(?:called|named)\s+[@/]?([a-zA-Z0-9_-]{1,64})\b",
        raw,
    )
    if m_cn and not specs:
        nm = m_cn.group(1).strip()
        specs.append((nm, _infer_domain(nm, raw)))

    if specs:
        return _dedupe_specs(specs)

    return []


def _fallback_registry_specs_from_explicit_nl(text: str) -> list[tuple[str, str]]:
    """Parse explicit legacy NL patterns (``create … agent called X``) into registry specs."""
    raw = (text or "").strip()
    if not raw:
        return []
    try:
        from app.services.custom_agent_parser import is_valid_user_agent_handle
        from app.services.custom_agent_routing import (
            _RE_ADD_CUSTOM_AGENT_AT,
            _RE_EXPLICIT_NAMED_AGENT,
            _RE_SETUP_AGENT_NAMED,
        )
    except ImportError:
        return []

    for rx in (_RE_EXPLICIT_NAMED_AGENT, _RE_ADD_CUSTOM_AGENT_AT, _RE_SETUP_AGENT_NAMED):
        m = rx.search(raw)
        if not m:
            continue
        nm = (m.group(1) or "").strip().lstrip("@")
        if nm and is_valid_user_agent_handle(nm):
            return [(nm, _infer_domain(nm, raw))]
    return []


def try_spawn_natural_sub_agents(
    db: Session | None,
    app_user_id: str,
    user_text: str,
    *,
    parent_chat_id: str,
) -> str | None:
    """
    Spawn sub-agents from natural language. Returns user-facing message or None if nothing to do.

    ``db`` is accepted for API symmetry; registry persists internally.
    """
    _ = db
    uid = (app_user_id or "").strip()
    if not uid or not prefers_registry_sub_agent(user_text):
        return None

    settings = get_settings()
    if not bool(getattr(settings, "nexa_agent_orchestration_enabled", False)):
        return (
            "Orchestration sub-agents are **off** on this deployment. "
            "Set **NEXA_AGENT_ORCHESTRATION_ENABLED=true** and restart, then try again."
        )

    specs = parse_natural_sub_agent_specs(user_text)
    if not specs:
        specs = _fallback_registry_specs_from_explicit_nl(user_text)
    if not specs:
        tl = user_text.lower()
        if "?" in tl or "help" in tl:
            return (
                "**Create agents**\n\n"
                "**Just say it naturally:**\n"
                "\u2022 \"Create a marketing agent\" \u00b7 \"I need a QA specialist\"\n"
                "\u2022 \"Set up a testing agent\" \u00b7 \"Can you create a security agent?\"\n\n"
                "**Or be specific:**\n"
                "\u2022 `create five agents: product_manager, designer, backend, frontend, qa`\n"
                "\u2022 `create two agents qa_agent and marketing_agent`\n\n"
                "Available types: **qa**, **marketing**, **git**, **vercel**, **railway**, **ops**, **test**, **security**.\n\n"
                "See your agents: `/subagent list`"
            )
        from app.services.intent_classifier import get_fallback_response
        return get_fallback_response(user_text)

    registry = AgentRegistry()
    tracker = get_activity_tracker()
    trusted = bool(getattr(settings, "nexa_agent_auto_approve", False))
    lines: list[str] = []

    for name, domain in specs:
        clean_name = name.strip().lstrip("@")[:64]
        dom = (domain or "general").strip().lower()[:32]
        if registry.get_agent_by_name(clean_name, parent_chat_id):
            lines.append(f"⚠️ @{clean_name} already exists in this scope.")
            continue
        spawned = registry.spawn_agent(
            clean_name,
            dom,
            parent_chat_id,
            trusted=trusted,
            owner_app_user_id=uid,
        )
        if not spawned:
            lines.append(
                f"❌ Could not create @{clean_name} (limit reached, duplicate, or registry blocked)."
            )
            continue
        tracker.log_action(
            agent_id=spawned.id,
            agent_name=spawned.name,
            action_type="created",
            metadata={"via": "natural_language_sub_agent", "parent_chat_id": parent_chat_id},
        )
        lines.append(f"✅ @{spawned.name} created (**{spawned.domain}**).")

    if not lines:
        return None
    lines.append("")
    lines.append("💡 Talk to your agents with `@name <request>` or say \"ask name to do something\".")
    return "\n".join(lines).strip()[:9000]


__all__ = [
    "looks_like_registry_agent_creation_nl",
    "normalize_sub_agent_domain",
    "parse_natural_sub_agent_specs",
    "prefers_registry_sub_agent",
    "try_spawn_natural_sub_agents",
]

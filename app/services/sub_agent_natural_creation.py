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
            "general",
        }
    )
    return k if k in known else "general"


def prefers_registry_sub_agent(text: str) -> bool:
    """
    True → route to orchestration sub-agent registry (Phase 48 single-system rule).

    Numbered/bullet-first lists stay off registry parsing (avoid greedy multi-line roster spam).
    """
    raw = (text or "").strip()
    tl = raw.lower()
    if "agent" not in tl:
        return False
    if not re.search(r"(?i)\b(create|make|add|build|spawn)\b", raw):
        return False
    if re.search(r"(?m)^\s*\d+[\).]\s+\S", raw):
        return False
    return True


def _infer_domain(name: str, full_text: str) -> str:
    """Pick registry domain from handle + message (Phase 47 — qa/marketing are first-class)."""
    n = (name or "").lower()
    ctx = (full_text or "").lower()
    blob = f"{n} {ctx}"

    # Name-first (handles like qa_agent, marketing_agent, security_expert)
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
        ):
            return prefix if prefix != "test" else "test"
    if n in ("qa", "qa_agent") or n.startswith("qa_"):
        return "qa"
    if "marketing" in n or n.startswith("market"):
        return "marketing"
    if "security" in n or n.startswith("sec_"):
        return "security"

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

    return normalize_sub_agent_domain(n.split("_")[0] if "_" in n else n)


def _clean_agent_chunk(chunk: str) -> str | None:
    c = chunk.strip().strip(".,;:")
    c = re.sub(r"(?i)\s+for\s+.+$", "", c).strip()
    c = re.sub(r"^[@/]+", "", c)
    if c and re.match(r"^[\w-]+$", c):
        return c[:64]
    return None


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


def parse_natural_sub_agent_specs(text: str) -> list[tuple[str, str]]:
    """Return (name, domain) pairs to spawn."""
    raw = (text or "").strip()
    if not raw:
        return []

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
    multi_m = re.search(
        r"(?is)\b(?:create|make|add|build|spawn)\s+(?:two|three|several|four|five|\d+\s+)?agents?\s*(?:[:,]?\s*)",
        raw,
    )
    if multi_m:
        tail = raw[multi_m.end() :].strip()
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
        # Dedupe by name preserving order
        seen: set[str] = set()
        out: list[tuple[str, str]] = []
        for nm, dom in specs:
            key = nm.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((nm, dom))
        return out

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
        return (
            "**Create orchestration agents**\n\n"
            "Examples:\n"
            "• `create two agents qa_agent and marketing_agent`\n"
            "• `create me a custom agent called legal-reviewer` — same registry\n"
            "• `subagent create ops_agent ops`\n"
            "• `create agent security_expert security`\n\n"
            "Domains include **qa**, **marketing**, **git**, **vercel**, **railway**, **ops**, **test**, **security**.\n\n"
            "View roster: `/subagent list` · Mission Control → **orchestration.sub_agents**."
        )

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
        spawned = registry.spawn_agent(clean_name, dom, parent_chat_id, trusted=trusted)
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
    lines.append("📋 **Team** — `/subagent list` · Mission Control → dashboard **orchestration.sub_agents**")
    return "\n".join(lines).strip()[:9000]


__all__ = [
    "normalize_sub_agent_domain",
    "parse_natural_sub_agent_specs",
    "prefers_registry_sub_agent",
    "try_spawn_natural_sub_agents",
]

from __future__ import annotations

import re
from typing import Any

# @mention token (lowercase) → vNext route key
_MENTION_ALIASES: dict[str, str] = {
    "reset": "reset",
    "overwhelm": "reset",
    "overwhelm_reset": "reset",
    "dev": "dev",
    "developer": "dev",
    "qa": "qa",
    "test": "qa",
    "strategy": "strategy",
    "ceo": "strategy",
    "cto": "strategy",
    "marketing": "marketing",
    "mkt": "marketing",
    "strat": "strategy",
    "research": "research",
    "ops": "ops",
    "nexa": "nexa",
    "person": "ops",
    "admin": "ops",
}

# Route key → internal agent_key
ROUTE_KEY_TO_INTERNAL: dict[str, str] = {
    "reset": "nexa",
    "dev": "developer",
    "qa": "qa",
    "strategy": "strategy",
    "marketing": "marketing",
    "research": "research",
    "ops": "ops",
    "nexa": "nexa",
    "mkt": "marketing",
    "strat": "strategy",
    "overwhelm": "nexa",
    "overwhelm_reset": "nexa",
    "person": "ops",
    "dev_legacy": "developer",  # unused
}


def map_route_key_to_internal(route: str) -> str:
    r = (route or "").lower().strip()
    return ROUTE_KEY_TO_INTERNAL.get(r, r)


def _registry_to_route(mention_key: str) -> str | None:
    """Map registry agent_key to vNext *route* key (before `map_route_key_to_internal`)."""
    k = (mention_key or "").lower().strip()
    m = {
        "developer": "dev",
        "nexa": "nexa",
        "overwhelm_reset": "reset",
        "qa": "qa",
        "marketing": "marketing",
        "strategy": "strategy",
        "research": "research",
        "ceo": "strategy",
        "cto": "strategy",
        "personal_admin": "ops",
    }
    return m.get(k)


def parse_agent_mention(text: str) -> tuple[str | None, str]:
    """
    Leading @mention → (catalog route key, remainder). Catalog keys: reset, dev, …
    Unknown or invalid @handles return (None, original text) so heuristics can run on the full string.
    """
    from app.services.mention_control import parse_mention

    t0 = (text or "").strip()
    mr = parse_mention(t0)
    if not mr.is_explicit:
        return None, t0
    if mr.error or not mr.agent_key:
        return None, t0
    return mr.agent_key, mr.text


def _out(
    agent_key: str,
    confidence: float,
    reason: str,
    *,
    text: str,
    routed: str | None = None,
) -> dict[str, Any]:
    return {
        "agent_key": agent_key,
        "confidence": float(confidence),
        "reason": reason,
        "routed_text": (routed if routed is not None else text).strip() or text,
    }


def route_agent(
    text: str, intent: str | None = None, context_snapshot: dict | None = None
) -> dict[str, Any]:
    t_raw = (text or "").strip()
    rkey, rem = parse_agent_mention(t_raw)
    _ = intent
    if rkey is not None:
        return _out(
            map_route_key_to_internal(rkey), 1.0, "explicit mention", text=t_raw, routed=rem
        )

    t = t_raw.lower()
    if re.search(
        r"\b(ask cursor|tell cursor|cursor|aider|fix code|refactor|ci failure|"
        r"autonomous dev|/improve|/dev\b|dev job|pull request|create branch)\b|\brepo\b",
        t,
    ):
        return _out("developer", 0.95, "dev phrase", text=t_raw)

    if re.search(
        r"\b(worker health|/dev health|dev health|check worker|ops check|is the worker|heartbeat)\b", t
    ):
        return _out("ops", 0.88, "ops phrase", text=t_raw)

    if re.search(
        r"\b(test failure|pytest|regression|qa|quality assurance|e2e|acceptance criteria|test plan)\b", t
    ) or (
        "test" in t
        and re.search(r"\b(fail|failing|broken|pytest|jest|jest)\b", t)
    ):
        if "regression" in t and "strategy" not in t and "roadmap" not in t and "positioning" not in t:
            return _out("qa", 0.8, "qa phrase", text=t_raw)
        return _out("qa", 0.9, "qa phrase", text=t_raw)

    if re.search(
        r"\b(roadmap|pricing|revenue|business model|milestone|stakeholder|okrs?|trade-?off|ceo)\b", t
    ):
        if re.search(
            r"\b(architecture|infrastructure|scale|threat|vendor|bottleneck|k8s|owasp|ddos)\b", t
        ):
            return _out("cto", 0.85, "technical phrase", text=t_raw)
        return _out("strategy", 0.86, "strategy phrase", text=t_raw)

    if re.search(
        r"\b(architecture|scalab|infrastructure|owasp|ddos|kubernetes|k8s|"
        r"system design|latency|bottleneck|threat model|vendor risk)\b",
        t,
    ):
        return _out("cto", 0.86, "cto phrase", text=t_raw)

    mkt = re.search(
        r"\b(landing|go-to-market|gtm|user persona|tweet|thread|newsletter|launch|campaign|"
        r"copy|positioning|marketing|launch copy|landing page)\b",
        t,
    )
    if mkt and "strategy" not in t and "roadmap" not in t and "stakeholder" not in t:
        return _out("marketing", 0.86, "marketing phrase", text=t_raw)

    if re.search(
        r"https?://",
        t_raw,
    ) or re.search(
        r"(?i)\b(visit|check|open|read|see|look at|summarize|what(?:'s| is) on|what products?)\b.{0,100}\b("
        r"web|url|page|site|this website|the site|that site)\b",
        t,
    ) or re.search(
        r"(?i)([a-z0-9](?:[a-z0-9-]{0,60}[a-z0-9])?\.)(?:com|io|app|org|net|dev|ai|co|us|tech)\b",
        t,
    ):
        return _out("research", 0.84, "url or public site inspection", text=t_raw)

    if re.search(
        r"\b(research|compare|competitor|citations?|sources?|latest|survey|market scan)\b", t
    ):
        return _out("research", 0.8, "research phrase", text=t_raw)

    if re.search(r"\b(inbox|calendar|schedul|errand|travel|receipt|remind me to)\b", t):
        return _out("personal_admin", 0.7, "ops-ish phrase", text=t_raw)

    if re.search(
        r"\b(overwhelmed|brain dump|too much|my brain|can\'?t focus|stuck|panic|drowning|anxious|freeze)\b", t
    ):
        return _out("nexa", 0.9, "reset phrase", text=t_raw)

    if context_snapshot and not context_snapshot.get("manual_topic_override"):
        act = context_snapshot.get("active_agent")
        if act:
            ak = str(act)
            if ak in ("overwhelm_reset", "reset", "overwhelm"):
                ak2 = "nexa"
            else:
                ak2 = ak
            if ak2 in {
                "developer",
                "qa",
                "nexa",
                "strategy",
                "marketing",
                "research",
                "cto",
                "ceo",
                "ops",
                "personal_admin",
                "general",
            }:
                return _out(ak2, 0.65, "conversation continuity", text=t_raw)

    return _out("nexa", 0.5, "default", text=t_raw)


def parse_leading_mention(text: str) -> tuple[str | None, str]:
    """(internal agent_key, body) e.g. developer, nexa, ops — or (None, text) if not a resolved @mention."""
    rkey, rem = parse_agent_mention((text or "").strip())
    if rkey is None:
        return None, (text or "").strip()
    return map_route_key_to_internal(rkey), rem


# --- Active agent projection (command-center visibility) --------------------------------
# NL routing order: slash → @mention → dev NL → ops → context → intent → default.

_AGENT_INFERENCE_META = (
    "which agent",
    "what agent",
    "which agents",
    "what agents",
    "who is handling",
    "handling what",
    "agent is handling",
    "which agent is handling what",
    "agents handle",
    "what are the agents",
    "list agents",
    "your agents",
    "nexa agents",
)


def infer_active_agents_from_text(text: str) -> list[str]:
    """
    Heuristic: which specialist lenses apply to the user’s message.
    Roster / “who is doing what” questions get a fixed command-center slice.
    """
    t = (text or "").lower()
    if any(phrase in t for phrase in _AGENT_INFERENCE_META):
        return ["strategy", "developer", "ops"]
    agents: list[str] = []
    if any(w in t for w in ("build", "code", "fix", "api", "backend")):
        agents.append("developer")
    if any(w in t for w in ("test", "bug", "validate")):
        agents.append("qa")
    if any(w in t for w in ("system", "health", "status", "infra")):
        agents.append("ops")
    if any(w in t for w in ("plan", "direction", "strategy", "future")):
        agents.append("strategy")
    if any(w in t for w in ("marketing", "brand", "position")):
        agents.append("marketing")
    if any(w in t for w in ("research", "compare")) or re.search(
        r"\blearn(ing)?\b", t
    ):
        agents.append("research")
    return agents or ["strategy"]


_PROJECTION_MAP: dict[str, str] = {
    "developer": "Developer → implementation & technical decisions",
    "qa": "QA → validation and testing",
    "ops": "Ops → worker health and execution state",
    "strategy": "Strategy → direction and planning",
    "marketing": "Marketing → positioning and messaging",
    "research": "Research → information and analysis",
}

_META_PROJECTION: tuple[str, str, str] = (
    "— Strategy → direction & planning",
    "— Developer → implementation & technical decisions",
    "— Ops → worker health and execution state",
)


def format_active_agent_projection(
    agents: list[str],
    active_topic: str | None = None,
) -> str:
    t = (active_topic or "").strip()[:200]
    head: list[str] = []
    if t:
        head.append(f"Active topic: {t}")
        head.append("")

    use_meta = set(agents) == {"strategy", "developer", "ops"}
    if use_meta:
        block = head + [
            "Active agents right now:",
            _META_PROJECTION[0],
            _META_PROJECTION[1],
            _META_PROJECTION[2],
        ]
        return "\n".join(block)

    seen: set[str] = set()
    lines: list[str] = []
    for a in agents:
        if a in _PROJECTION_MAP and a not in seen:
            seen.add(a)
            lines.append(f"— {_PROJECTION_MAP[a]}")
    if not lines:
        lines = [f"— {_PROJECTION_MAP['strategy']}"]
    return "\n".join(head + ["Active agents right now:", *lines])


def should_emit_active_agent_projection(intent: str, text: str) -> bool:
    """
    Only for explicit *agent roster* questions, not command lists or general capability.
    """
    if intent == "brain_dump":
        return False
    t = (text or "").lower()
    if "which agent" in t:
        return True
    if "who is handling" in t:
        return True
    if "which agent is" in t:
        return True
    return False
